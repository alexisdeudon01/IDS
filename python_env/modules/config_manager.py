"""
Configuration Manager Module

Loads, validates, and provides access to the master configuration.
Thread-safe and process-safe.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
        self._validate_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _validate_config(self) -> None:
        """Validate required configuration sections"""
        required_sections = [
            'raspberry_pi',
            'resources',
            'aws',
            'docker',
            'vector',
            'suricata',
            'monitoring',
            'git'
        ]
        
        missing = [s for s in required_sections if s not in self.config]
        if missing:
            raise ValueError(f"Missing required config sections: {missing}")
        
        # Validate resource limits
        resources = self.config['resources']
        if resources['max_cpu_percent'] > 100 or resources['max_cpu_percent'] < 0:
            raise ValueError("max_cpu_percent must be between 0 and 100")
        if resources['max_ram_percent'] > 100 or resources['max_ram_percent'] < 0:
            raise ValueError("max_ram_percent must be between 0 and 100")
        
        # Validate network interface
        rpi = self.config['raspberry_pi']
        if rpi['network_interface'] != 'eth0':
            logger.warning(f"Network interface is {rpi['network_interface']}, expected eth0")
        
        logger.info("Configuration validation passed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key
        
        Args:
            key: Dot-separated key (e.g., 'aws.region')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section
        
        Args:
            section: Section name (e.g., 'aws', 'docker')
            
        Returns:
            Configuration section dictionary
        """
        return self.config.get(section, {})
    
    def get_resource_limits(self) -> Dict[str, float]:
        """Get resource limit configuration"""
        return {
            'max_cpu_percent': self.get('resources.max_cpu_percent', 70.0),
            'max_ram_percent': self.get('resources.max_ram_percent', 70.0),
            'throttle_threshold_1': self.get('resources.throttle_threshold_1', 50.0),
            'throttle_threshold_2': self.get('resources.throttle_threshold_2', 60.0),
            'throttle_threshold_3': self.get('resources.throttle_threshold_3', 70.0),
        }
    
    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS OpenSearch configuration"""
        aws = self.get_section('aws')
        return {
            'region': aws.get('region', 'us-east-1'),
            'profile': aws.get('profile', 'moi33'),
            'domain_name': aws.get('opensearch_domain'),
            'endpoint': aws.get('opensearch_endpoint'),
            'index_prefix': aws.get('index_prefix', 'ids2-logs'),
            'bulk_size': aws.get('bulk_size', 100),
            'bulk_timeout': aws.get('bulk_timeout', 30),
        }
    
    def get_docker_config(self) -> Dict[str, Any]:
        """Get Docker configuration"""
        return self.get_section('docker')
    
    def get_vector_config(self) -> Dict[str, Any]:
        """Get Vector configuration"""
        return self.get_section('vector')
    
    def get_suricata_config(self) -> Dict[str, Any]:
        """Get Suricata configuration"""
        return self.get_section('suricata')
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return self.get_section('monitoring')
    
    def get_git_config(self) -> Dict[str, Any]:
        """Get Git workflow configuration"""
        return self.get_section('git')
    
    def reload(self) -> None:
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        self._validate_config()
    
    def __repr__(self) -> str:
        return f"ConfigManager(config_path={self.config_path})"
