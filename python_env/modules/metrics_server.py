"""
Metrics Server Module (Process #4)

Exposes Prometheus metrics on port 9100.
Publishes system metrics, pipeline metrics, and health status.

This runs as a separate process.
"""

import time
import logging
from typing import Dict, Any
from multiprocessing import Process
from prometheus_client import (
    start_http_server,
    Gauge,
    Counter,
    Histogram,
    Info
)

logger = logging.getLogger(__name__)


class MetricsServer:
    """Prometheus metrics exporter"""
    
    def __init__(self, config_manager, shared_state: Dict[str, Any]):
        """
        Initialize metrics server
        
        Args:
            config_manager: Configuration manager instance
            shared_state: Shared state dictionary from multiprocessing.Manager()
        """
        self.config = config_manager
        self.shared_state = shared_state
        self.monitoring_config = config_manager.get_monitoring_config()
        
        # Server configuration
        self.port = self.monitoring_config.get('prometheus_port', 9100)
        self.host = '0.0.0.0'
        
        # Update interval
        self.update_interval = 5.0  # seconds
        
        # Process reference
        self.process: Process = None
        
        # Metrics (defined in _setup_metrics)
        self.metrics = {}
    
    def _setup_metrics(self) -> None:
        """
        Setup Prometheus metrics
        
        This must be called within the metrics process to avoid
        multiprocessing issues with prometheus_client.
        """
        # System metrics
        self.metrics['cpu_usage'] = Gauge(
            'ids2_cpu_usage_percent',
            'Current CPU usage percentage'
        )
        
        self.metrics['ram_usage'] = Gauge(
            'ids2_ram_usage_percent',
            'Current RAM usage percentage'
        )
        
        self.metrics['throttle_level'] = Gauge(
            'ids2_throttle_level',
            'Current throttling level (0-3)'
        )
        
        # Connectivity metrics
        self.metrics['dns_status'] = Gauge(
            'ids2_dns_status',
            'DNS connectivity status (1=ok, 0=fail)'
        )
        
        self.metrics['tls_status'] = Gauge(
            'ids2_tls_status',
            'TLS connectivity status (1=ok, 0=fail)'
        )
        
        self.metrics['opensearch_status'] = Gauge(
            'ids2_opensearch_status',
            'OpenSearch connectivity status (1=ok, 0=fail)'
        )
        
        self.metrics['aws_ready'] = Gauge(
            'ids2_aws_ready',
            'AWS overall readiness (1=ready, 0=not ready)'
        )
        
        # Pipeline metrics
        self.metrics['vector_status'] = Gauge(
            'ids2_vector_status',
            'Vector service status (1=running, 0=stopped)'
        )
        
        self.metrics['suricata_status'] = Gauge(
            'ids2_suricata_status',
            'Suricata service status (1=running, 0=stopped)'
        )
        
        self.metrics['redis_status'] = Gauge(
            'ids2_redis_status',
            'Redis service status (1=running, 0=stopped)'
        )
        
        self.metrics['pipeline_ok'] = Gauge(
            'ids2_pipeline_ok',
            'Overall pipeline health (1=ok, 0=degraded)'
        )
        
        # Counters
        self.metrics['events_processed'] = Counter(
            'ids2_events_processed_total',
            'Total number of events processed'
        )
        
        self.metrics['events_failed'] = Counter(
            'ids2_events_failed_total',
            'Total number of events that failed processing'
        )
        
        self.metrics['gc_forced'] = Counter(
            'ids2_gc_forced_total',
            'Total number of forced garbage collections'
        )
        
        # Histograms
        self.metrics['ingestion_latency'] = Histogram(
            'ids2_ingestion_latency_seconds',
            'Latency of event ingestion to OpenSearch',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        # Info
        self.metrics['build_info'] = Info(
            'ids2_build',
            'Build information'
        )
        self.metrics['build_info'].info({
            'version': '1.0.0',
            'platform': 'raspberry_pi_5',
            'architecture': 'aarch64'
        })
        
        logger.info("Prometheus metrics initialized")
    
    def _update_metrics(self) -> None:
        """
        Update metrics from shared state
        
        Reads values from shared_state and updates Prometheus metrics.
        """
        try:
            # System metrics
            self.metrics['cpu_usage'].set(
                self.shared_state.get('cpu_percent', 0.0)
            )
            self.metrics['ram_usage'].set(
                self.shared_state.get('ram_percent', 0.0)
            )
            self.metrics['throttle_level'].set(
                self.shared_state.get('throttle_level', 0)
            )
            
            # Connectivity metrics
            self.metrics['dns_status'].set(
                1 if self.shared_state.get('dns_ok', False) else 0
            )
            self.metrics['tls_status'].set(
                1 if self.shared_state.get('tls_ok', False) else 0
            )
            self.metrics['opensearch_status'].set(
                1 if self.shared_state.get('opensearch_ok', False) else 0
            )
            self.metrics['aws_ready'].set(
                1 if self.shared_state.get('aws_ready', False) else 0
            )
            
            # Pipeline metrics
            self.metrics['vector_status'].set(
                1 if self.shared_state.get('vector_running', False) else 0
            )
            self.metrics['suricata_status'].set(
                1 if self.shared_state.get('suricata_running', False) else 0
            )
            self.metrics['redis_status'].set(
                1 if self.shared_state.get('redis_running', False) else 0
            )
            self.metrics['pipeline_ok'].set(
                1 if self.shared_state.get('pipeline_ok', False) else 0
            )
            
            # Update counters if values changed
            events_processed = self.shared_state.get('events_processed', 0)
            events_failed = self.shared_state.get('events_failed', 0)
            
            # Note: Counters can only increment, so we track the delta
            # This is a simplified approach; in production, use proper counter tracking
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    def _metrics_loop(self) -> None:
        """
        Main metrics loop (runs in separate process)
        
        This is the entry point for Process #4.
        """
        logger.info(f"Metrics server process started")
        
        try:
            # Setup metrics (must be done in this process)
            self._setup_metrics()
            
            # Start HTTP server
            start_http_server(self.port, addr=self.host)
            logger.info(f"Prometheus metrics server listening on {self.host}:{self.port}")
            
            # Update loop
            while True:
                self._update_metrics()
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("Metrics server received shutdown signal")
        except Exception as e:
            logger.error(f"Metrics server error: {e}", exc_info=True)
    
    def start(self) -> None:
        """Start metrics server process"""
        if self.process and self.process.is_alive():
            logger.warning("Metrics server already running")
            return
        
        self.process = Process(
            target=self._metrics_loop,
            name="MetricsServer"
        )
        self.process.start()
        logger.info(f"Metrics server started (PID: {self.process.pid})")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop metrics server process
        
        Args:
            timeout: Maximum time to wait for process to stop
        """
        if not self.process or not self.process.is_alive():
            logger.warning("Metrics server not running")
            return
        
        logger.info("Stopping metrics server...")
        self.process.terminate()
        self.process.join(timeout=timeout)
        
        if self.process.is_alive():
            logger.warning("Metrics server did not stop gracefully, killing...")
            self.process.kill()
            self.process.join()
        
        logger.info("Metrics server stopped")
    
    def is_alive(self) -> bool:
        """Check if metrics server process is alive"""
        return self.process and self.process.is_alive()
