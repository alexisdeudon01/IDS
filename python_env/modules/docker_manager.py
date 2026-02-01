"""
Docker Manager Module

Manages Docker Compose stack lifecycle (Vector, Redis, Prometheus, Grafana).
Monitors container health and resource usage.
"""

import os
import time
import logging
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import docker
    from docker.errors import DockerException, APIError
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False
    logging.warning("Docker SDK not available, using CLI fallback")

logger = logging.getLogger(__name__)


class DockerManager:
    """Manages Docker Compose stack"""
    
    def __init__(self, config_manager):
        """
        Initialize Docker manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.docker_config = config_manager.get_docker_config()
        
        # Docker Compose file path
        self.compose_file = Path(self.docker_config.get('compose_file', 'docker/docker-compose.yml'))
        
        # Docker client (if SDK available)
        self.client = None
        if DOCKER_SDK_AVAILABLE:
            try:
                self.client = docker.from_env()
                logger.info("Docker SDK client initialized")
            except DockerException as e:
                logger.warning(f"Failed to initialize Docker SDK: {e}")
                self.client = None
        
        # Service names
        self.services = ['vector', 'redis', 'prometheus', 'grafana']
    
    def _run_compose_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run docker-compose command
        
        Args:
            command: Command arguments (e.g., ['up', '-d'])
            check: Whether to raise exception on non-zero exit
            
        Returns:
            CompletedProcess result
        """
        cmd = ['docker-compose', '-f', str(self.compose_file)] + command
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            
            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr}")
            
            return result
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def verify_compose_file(self) -> bool:
        """
        Verify docker-compose.yml exists and is valid
        
        Returns:
            True if valid
        """
        if not self.compose_file.exists():
            logger.error(f"Docker Compose file not found: {self.compose_file}")
            return False
        
        try:
            result = self._run_compose_command(['config', '--quiet'], check=False)
            if result.returncode == 0:
                logger.info("Docker Compose file is valid")
                return True
            else:
                logger.error("Docker Compose file validation failed")
                return False
        except Exception as e:
            logger.error(f"Error validating Compose file: {e}")
            return False
    
    def start_stack(self, pull: bool = True) -> bool:
        """
        Start Docker Compose stack
        
        Args:
            pull: Whether to pull images first
            
        Returns:
            True if successful
        """
        try:
            logger.info("Starting Docker Compose stack...")
            
            # Pull images if requested
            if pull:
                logger.info("Pulling Docker images...")
                self._run_compose_command(['pull'])
            
            # Start services
            logger.info("Starting services...")
            self._run_compose_command(['up', '-d'])
            
            logger.info("Docker Compose stack started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Docker stack: {e}")
            return False
    
    def stop_stack(self, timeout: int = 30) -> bool:
        """
        Stop Docker Compose stack
        
        Args:
            timeout: Timeout for stopping containers
            
        Returns:
            True if successful
        """
        try:
            logger.info("Stopping Docker Compose stack...")
            self._run_compose_command(['down', '--timeout', str(timeout)])
            logger.info("Docker Compose stack stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Docker stack: {e}")
            return False
    
    def restart_service(self, service: str) -> bool:
        """
        Restart a specific service
        
        Args:
            service: Service name (e.g., 'vector', 'redis')
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Restarting service: {service}")
            self._run_compose_command(['restart', service])
            logger.info(f"Service {service} restarted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart service {service}: {e}")
            return False
    
    def get_service_status(self, service: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific service
        
        Args:
            service: Service name
            
        Returns:
            Status dictionary or None if not found
        """
        try:
            result = self._run_compose_command(['ps', '--format', 'json', service], check=False)
            
            if result.returncode == 0 and result.stdout:
                import json
                # Parse JSON output
                status_list = json.loads(result.stdout)
                if status_list:
                    return status_list[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return None
    
    def is_service_running(self, service: str) -> bool:
        """
        Check if a service is running
        
        Args:
            service: Service name
            
        Returns:
            True if running
        """
        status = self.get_service_status(service)
        if status:
            state = status.get('State', '').lower()
            return state == 'running'
        return False
    
    def wait_for_service_healthy(
        self,
        service: str,
        max_wait: int = 60,
        check_interval: int = 5
    ) -> bool:
        """
        Wait for a service to become healthy
        
        Args:
            service: Service name
            max_wait: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            
        Returns:
            True if service becomes healthy
        """
        logger.info(f"Waiting for {service} to be healthy (max {max_wait}s)...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait:
            if self.is_service_running(service):
                # Additional health check could be done here
                logger.info(f"Service {service} is running")
                return True
            
            logger.debug(f"Service {service} not ready yet, waiting {check_interval}s...")
            time.sleep(check_interval)
        
        logger.error(f"Timeout waiting for service {service}")
        return False
    
    def wait_for_stack_healthy(self, max_wait: int = 120) -> bool:
        """
        Wait for entire stack to be healthy
        
        Args:
            max_wait: Maximum time to wait in seconds
            
        Returns:
            True if all services are healthy
        """
        logger.info("Waiting for Docker stack to be healthy...")
        
        for service in self.services:
            if not self.wait_for_service_healthy(service, max_wait=max_wait):
                logger.error(f"Service {service} failed to become healthy")
                return False
        
        logger.info("All Docker services are healthy")
        return True
    
    def get_stack_status(self) -> Dict[str, bool]:
        """
        Get status of all services in stack
        
        Returns:
            Dictionary mapping service names to running status
        """
        status = {}
        for service in self.services:
            status[service] = self.is_service_running(service)
        return status
    
    def get_container_logs(self, service: str, tail: int = 50) -> Optional[str]:
        """
        Get logs from a service container
        
        Args:
            service: Service name
            tail: Number of lines to retrieve
            
        Returns:
            Log output or None
        """
        try:
            result = self._run_compose_command(
                ['logs', '--tail', str(tail), service],
                check=False
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting logs for {service}: {e}")
            return None
    
    def get_container_stats(self, service: str) -> Optional[Dict[str, Any]]:
        """
        Get resource usage stats for a service
        
        Args:
            service: Service name
            
        Returns:
            Stats dictionary or None
        """
        if not self.client:
            logger.warning("Docker SDK not available, cannot get stats")
            return None
        
        try:
            # Get container by service name
            containers = self.client.containers.list(
                filters={'label': f'com.docker.compose.service={service}'}
            )
            
            if not containers:
                return None
            
            container = containers[0]
            stats = container.stats(stream=False)
            
            # Parse stats
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
            
            mem_usage = stats['memory_stats']['usage']
            mem_limit = stats['memory_stats']['limit']
            mem_percent = (mem_usage / mem_limit) * 100.0
            
            return {
                'cpu_percent': cpu_percent,
                'mem_usage_mb': mem_usage / (1024 * 1024),
                'mem_limit_mb': mem_limit / (1024 * 1024),
                'mem_percent': mem_percent
            }
            
        except Exception as e:
            logger.error(f"Error getting stats for {service}: {e}")
            return None
    
    def cleanup(self, volumes: bool = False) -> bool:
        """
        Clean up Docker resources
        
        Args:
            volumes: Whether to remove volumes
            
        Returns:
            True if successful
        """
        try:
            logger.info("Cleaning up Docker resources...")
            
            cmd = ['down']
            if volumes:
                cmd.append('--volumes')
            
            self._run_compose_command(cmd)
            logger.info("Docker cleanup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup Docker resources: {e}")
            return False
