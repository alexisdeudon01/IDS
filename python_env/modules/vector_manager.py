"""
Vector Manager Module

Generates Vector configuration and manages Vector lifecycle.
Handles ECS transformation, Redis fallback, and bulk batching.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VectorManager:
    """Manages Vector configuration and operations"""
    
    def __init__(self, config_manager):
        """
        Initialize Vector manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.vector_config = config_manager.get_vector_config()
        self.aws_config = config_manager.get_aws_config()
        
        # Configuration file path
        self.config_file = Path(self.vector_config.get('config_file', 'vector/vector.toml'))
    
    def generate_config(self) -> bool:
        """
        Generate Vector configuration file
        
        Returns:
            True if successful
        """
        try:
            logger.info("Generating Vector configuration...")
            
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Build configuration
            config_content = self._build_config_content()
            
            # Write to file
            with open(self.config_file, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Vector configuration written to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate Vector configuration: {e}")
            return False
    
    def _build_config_content(self) -> str:
        """
        Build Vector configuration content in TOML format
        
        Returns:
            Configuration content as string
        """
        # Get configuration values
        log_file = self.vector_config.get('log_file', '/mnt/ram_logs/eve.json')
        buffer_dir = self.vector_config.get('buffer_dir', '/var/lib/vector/buffer')
        redis_url = self.vector_config.get('redis_url', 'redis://redis:6379/0')
        opensearch_endpoint = self.aws_config.get('endpoint', '')
        index_prefix = self.aws_config.get('index_prefix', 'ids2-logs')
        bulk_size = self.aws_config.get('bulk_size', 100)
        bulk_timeout = self.aws_config.get('bulk_timeout', 30)
        buffer_max_size_bytes = self.vector_config.get('buffer_max_size_bytes', 268435456)  # Default to 256MB
        
        # Build TOML configuration
        config = f'''# Vector Configuration for IDS2 SOC Pipeline
# Generated automatically - DO NOT EDIT MANUALLY

# Data directory
data_dir = "/var/lib/vector"

# ============================================================================
# SOURCES
# ============================================================================

# Source: Read Suricata eve.json logs
[sources.suricata_logs]
type = "file"
include = ["{log_file}"]
read_from = "end"
fingerprint.strategy = "device_and_inode"
max_line_bytes = 102400  # 100KB max line size

# ============================================================================
# TRANSFORMS
# ============================================================================

# Transform: Parse JSON
[transforms.parse_json]
type = "remap"
inputs = ["suricata_logs"]
source = """
. = parse_json!(.message)
"""

# Transform: Add ECS fields
[transforms.add_ecs_fields]
type = "remap"
inputs = ["parse_json"]
source = """
# ECS base fields
.@timestamp = .timestamp
.ecs.version = "8.0.0"

# Event fields
.event.kind = "event"
.event.category = ["network"]
.event.type = ["connection"]
.event.dataset = "suricata.eve"
.event.module = "suricata"

# Source/Destination
if exists(.src_ip) {{
    .source.ip = .src_ip
    .source.port = .src_port
}}

if exists(.dest_ip) {{
    .destination.ip = .dest_ip
    .destination.port = .dest_port
}}

# Network fields
if exists(.proto) {{
    .network.protocol = downcase(.proto)
}}

# Alert fields (if present)
if exists(.alert) {{
    .event.kind = "alert"
    .event.category = ["intrusion_detection"]
    .rule.name = .alert.signature
    .rule.id = to_string(.alert.signature_id)
    .event.severity = .alert.severity
}}

# Add metadata
.agent.type = "vector"
.agent.version = "0.34.0"
.host.hostname = "raspberrypi5"
.host.architecture = "aarch64"

# Clean up original fields (optional)
del(.message)
"""

# Transform: Add index routing
[transforms.route_to_index]
type = "remap"
inputs = ["add_ecs_fields"]
source = """
# Generate index name based on date
.index_name = "{index_prefix}-" + format_timestamp!(.@timestamp, format: "%Y.%m.%d")
"""

# ============================================================================
# SINKS
# ============================================================================

# Sink: OpenSearch (primary)
[sinks.opensearch]
type = "elasticsearch"
inputs = ["route_to_index"]
endpoint = "{opensearch_endpoint}"
mode = "bulk"
bulk.index = "{{{{ index_name }}}}"
bulk.action = "create"
compression = "gzip"

# Batch settings (optimized for Raspberry Pi)
batch.max_events = {bulk_size}
batch.timeout_secs = {bulk_timeout}

# Buffer settings (disk-based for reliability)
buffer.type = "disk"
buffer.max_size = {buffer_max_size_bytes}
buffer.when_full = "block"

# Request settings
request.timeout_secs = 60
request.retry_attempts = 3
request.retry_initial_backoff_secs = 2
request.retry_max_duration_secs = 300

# Health check
healthcheck.enabled = true
healthcheck.uri = "{opensearch_endpoint}/_cluster/health"

# Encoding
encoding.codec = "json"

# TLS (disable verification for testing; enable in production)
tls.verify_certificate = false
tls.verify_hostname = false

# ============================================================================
# Sink: Redis (fallback buffer)
# ============================================================================

[sinks.redis_fallback]
type = "redis"
inputs = ["route_to_index"]
url = "{redis_url}"
key = "vector:fallback:{{{{ index_name }}}}"
data_type = "list"
list.method = "rpush"

# Batch settings
batch.max_events = 50
batch.timeout_secs = 10

# Encoding
encoding.codec = "json"

# Only use when OpenSearch is unavailable
# This requires Vector 0.34+ with conditional routing

# ============================================================================
# INTERNAL METRICS
# ============================================================================

# Expose internal metrics for Prometheus
[sources.internal_metrics]
type = "internal_metrics"

[sinks.prometheus_exporter]
type = "prometheus_exporter"
inputs = ["internal_metrics"]
address = "0.0.0.0:9101"
default_namespace = "vector"

# ============================================================================
# LOGGING
# ============================================================================

[log_schema]
host_key = "host"
message_key = "message"
timestamp_key = "@timestamp"
'''
        
        return config
    
    def validate_config(self) -> bool:
        """
        Validate Vector configuration file
        
        Returns:
            True if valid
        """
        if not self.config_file.exists():
            logger.error(f"Vector config file not found: {self.config_file}")
            return False
        
        # Vector has a validate command, but we'll do basic checks
        try:
            with open(self.config_file, 'r') as f:
                content = f.read()
            
            # Basic validation - check for required sections
            required_sections = ['sources.suricata_logs', 'sinks.opensearch']
            for section in required_sections:
                if section not in content:
                    logger.error(f"Missing required section: {section}")
                    return False
            
            logger.info("Vector configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating Vector config: {e}")
            return False
    
    def get_health_status(self) -> Optional[Dict[str, Any]]:
        """
        Get Vector health status via API
        
        Returns:
            Health status dictionary or None
        """
        # Vector exposes health on port 8686 by default
        # This would use requests to query the health endpoint
        # For now, this is a placeholder
        logger.debug("Vector health check would be implemented here")
        return None
    
    def reload_config(self) -> bool:
        """
        Reload Vector configuration (send SIGHUP)
        
        Returns:
            True if successful
        """
        # This would send SIGHUP to Vector process
        # For now, this is a placeholder
        logger.info("Vector config reload would be implemented here")
        return True
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Get Vector internal metrics
        
        Returns:
            Metrics dictionary or None
        """
        # Query Vector's Prometheus exporter on port 9101
        # For now, this is a placeholder
        logger.debug("Vector metrics query would be implemented here")
        return None
    
    def estimate_buffer_usage(self) -> Optional[Dict[str, Any]]:
        """
        Estimate disk buffer usage
        
        Returns:
            Buffer usage statistics or None
        """
        buffer_dir = Path(self.vector_config.get('buffer_dir', '/var/lib/vector/buffer'))
        
        if not buffer_dir.exists():
            return None
        
        try:
            total_size = 0
            file_count = 0
            
            for file in buffer_dir.rglob('*'):
                if file.is_file():
                    total_size += file.stat().st_size
                    file_count += 1
            
            return {
                'total_size_mb': total_size / (1024 * 1024),
                'file_count': file_count,
                'buffer_dir': str(buffer_dir)
            }
            
        except Exception as e:
            logger.error(f"Error estimating buffer usage: {e}")
            return None
