"""
Connectivity Checker Module (Process #3)

Asynchronous connectivity verification using asyncio + uvloop.
Runs DNS resolution, TLS handshake, and OpenSearch bulk tests in parallel.

This runs as a separate process and updates shared state.
"""

import asyncio
import logging
import time
import socket
import ssl
from typing import Dict, Any, Optional, Tuple
from multiprocessing import Process

try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False
    logging.warning("uvloop not available, using default asyncio loop")

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)


class ConnectivityChecker:
    """Asynchronous connectivity verification"""
    
    def __init__(self, config_manager, shared_state: Dict[str, Any]):
        """
        Initialize connectivity checker
        
        Args:
            config_manager: Configuration manager instance
            shared_state: Shared state dictionary from multiprocessing.Manager()
        """
        self.config = config_manager
        self.shared_state = shared_state
        self.aws_config = config_manager.get_aws_config()
        
        # Check interval
        self.check_interval = 30.0  # seconds
        
        # Process reference
        self.process: Process = None
        
        # Initialize shared state
        self.shared_state['dns_ok'] = False
        self.shared_state['tls_ok'] = False
        self.shared_state['opensearch_ok'] = False
        self.shared_state['aws_ready'] = False
        self.shared_state['last_connectivity_check'] = 0
    
    async def _check_dns(self, hostname: str) -> Tuple[bool, Optional[str]]:
        """
        Check DNS resolution
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            Tuple of (success, ip_address or error_message)
        """
        try:
            loop = asyncio.get_event_loop()
            # Resolve hostname
            result = await loop.getaddrinfo(
                hostname, 443,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM
            )
            
            if result:
                ip = result[0][4][0]
                logger.info(f"DNS resolution successful: {hostname} -> {ip}")
                return True, ip
            else:
                return False, "No DNS results"
                
        except Exception as e:
            logger.error(f"DNS resolution failed for {hostname}: {e}")
            return False, str(e)
    
    async def _check_tls(self, hostname: str, port: int = 443) -> Tuple[bool, Optional[str]]:
        """
        Check TLS handshake
        
        Args:
            hostname: Hostname to connect to
            port: Port number (default 443)
            
        Returns:
            Tuple of (success, error_message if failed)
        """
        try:
            # Create SSL context
            ssl_context = ssl.create_default_context()
            
            # Open connection with TLS
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    hostname, port,
                    ssl=ssl_context,
                    server_hostname=hostname
                ),
                timeout=10.0
            )
            
            # Get peer certificate
            ssl_object = writer.get_extra_info('ssl_object')
            if ssl_object:
                cert = ssl_object.getpeercert()
                logger.info(f"TLS handshake successful with {hostname}")
                logger.debug(f"Certificate subject: {cert.get('subject')}")
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            return True, None
            
        except asyncio.TimeoutError:
            logger.error(f"TLS handshake timeout for {hostname}:{port}")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"TLS handshake failed for {hostname}:{port}: {e}")
            return False, str(e)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _check_opensearch_bulk(self, endpoint: str) -> Tuple[bool, Optional[str]]:
        """
        Check OpenSearch bulk API endpoint
        
        Args:
            endpoint: OpenSearch endpoint URL
            
        Returns:
            Tuple of (success, error_message if failed)
        """
        try:
            # Prepare test bulk request (minimal)
            test_data = '{"index":{"_index":"test"}}\n{"test":"connectivity"}\n'
            
            url = f"{endpoint}/_bulk"
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    data=test_data,
                    headers={'Content-Type': 'application/x-ndjson'},
                    ssl=False  # For testing; in production use proper SSL verification
                ) as response:
                    
                    if response.status in [200, 201]:
                        result = await response.json()
                        logger.info(f"OpenSearch bulk test successful: {url}")
                        logger.debug(f"Bulk response: {result}")
                        return True, None
                    else:
                        error = f"HTTP {response.status}"
                        logger.error(f"OpenSearch bulk test failed: {error}")
                        return False, error
                        
        except asyncio.TimeoutError:
            logger.error(f"OpenSearch bulk test timeout: {endpoint}")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"OpenSearch bulk test failed: {e}")
            return False, str(e)
    
    async def _run_all_checks(self) -> None:
        """
        Run all connectivity checks in parallel
        
        This is the core async function that runs DNS, TLS, and bulk tests concurrently.
        """
        endpoint = self.aws_config.get('endpoint')
        
        if not endpoint:
            logger.error("No OpenSearch endpoint configured")
            self.shared_state['aws_ready'] = False
            return
        
        # Extract hostname from endpoint
        hostname = endpoint.replace('https://', '').replace('http://', '').split('/')[0]
        
        logger.info(f"Running connectivity checks for {hostname}...")
        
        # Run checks in parallel
        dns_task = self._check_dns(hostname)
        tls_task = self._check_tls(hostname)
        
        # Wait for DNS and TLS first
        dns_result, tls_result = await asyncio.gather(
            dns_task, tls_task,
            return_exceptions=True
        )
        
        # Update shared state
        if isinstance(dns_result, tuple):
            self.shared_state['dns_ok'] = dns_result[0]
        else:
            self.shared_state['dns_ok'] = False
            logger.error(f"DNS check exception: {dns_result}")
        
        if isinstance(tls_result, tuple):
            self.shared_state['tls_ok'] = tls_result[0]
        else:
            self.shared_state['tls_ok'] = False
            logger.error(f"TLS check exception: {tls_result}")
        
        # Only run bulk test if DNS and TLS succeeded
        if self.shared_state['dns_ok'] and self.shared_state['tls_ok']:
            try:
                bulk_result = await self._check_opensearch_bulk(endpoint)
                self.shared_state['opensearch_ok'] = bulk_result[0]
            except Exception as e:
                logger.error(f"Bulk check exception: {e}")
                self.shared_state['opensearch_ok'] = False
        else:
            logger.warning("Skipping bulk test due to DNS/TLS failure")
            self.shared_state['opensearch_ok'] = False
        
        # Update overall AWS readiness
        self.shared_state['aws_ready'] = (
            self.shared_state['dns_ok'] and
            self.shared_state['tls_ok'] and
            self.shared_state['opensearch_ok']
        )
        
        self.shared_state['last_connectivity_check'] = time.time()
        
        # Log summary
        logger.info(
            f"Connectivity check complete - "
            f"DNS: {self.shared_state['dns_ok']}, "
            f"TLS: {self.shared_state['tls_ok']}, "
            f"Bulk: {self.shared_state['opensearch_ok']}, "
            f"AWS Ready: {self.shared_state['aws_ready']}"
        )
    
    async def _monitor_loop(self) -> None:
        """
        Main monitoring loop (async)
        
        Periodically runs connectivity checks.
        """
        logger.info("Connectivity checker started")
        
        try:
            while True:
                await self._run_all_checks()
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("Connectivity checker cancelled")
        except Exception as e:
            logger.error(f"Connectivity checker error: {e}", exc_info=True)
    
    def _run_async_loop(self) -> None:
        """
        Entry point for Process #3
        
        Sets up uvloop (if available) and runs the async monitor loop.
        """
        # Use uvloop if available for better performance
        if UVLOOP_AVAILABLE:
            uvloop.install()
            logger.info("Using uvloop for async operations")
        
        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._monitor_loop())
        except KeyboardInterrupt:
            logger.info("Connectivity checker received shutdown signal")
        finally:
            loop.close()
    
    def start(self) -> None:
        """Start connectivity checking process"""
        if self.process and self.process.is_alive():
            logger.warning("Connectivity checker already running")
            return
        
        self.process = Process(
            target=self._run_async_loop,
            name="ConnectivityChecker"
        )
        self.process.start()
        logger.info(f"Connectivity checker started (PID: {self.process.pid})")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop connectivity checking process
        
        Args:
            timeout: Maximum time to wait for process to stop
        """
        if not self.process or not self.process.is_alive():
            logger.warning("Connectivity checker not running")
            return
        
        logger.info("Stopping connectivity checker...")
        self.process.terminate()
        self.process.join(timeout=timeout)
        
        if self.process.is_alive():
            logger.warning("Connectivity checker did not stop gracefully, killing...")
            self.process.kill()
            self.process.join()
        
        logger.info("Connectivity checker stopped")
    
    def is_alive(self) -> bool:
        """Check if connectivity checker process is alive"""
        return self.process and self.process.is_alive()
