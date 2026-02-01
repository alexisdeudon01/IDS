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

try:
    from modules.env_utils import resolve_env_placeholder, validate_env_placeholder
except ImportError:
    from env_utils import resolve_env_placeholder, validate_env_placeholder

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
            'git',
            'opensearch_credentials',
            'opensearch_creation',
            'raspberry_pi_remote',
            'testing',
            'features',
            'timeouts',
            'retry',
            'health_checks'
        ]
        
        missing = [s for s in required_sections if s not in self.config]
        if missing:
            raise ValueError(f"Missing required config sections: {missing}")
        
        # Validate resource limits
        resources = self.config['resources']
        if not (0 <= resources['max_cpu_percent'] <= 100):
            raise ValueError("max_cpu_percent must be between 0 and 100")
        if not (0 <= resources['max_ram_percent'] <= 100):
            raise ValueError("max_ram_percent must be between 0 and 100")
        
        # Validate network interface
        rpi = self.config['raspberry_pi']
        if rpi.get('network_interface') != 'eth0':
            logger.warning(f"Network interface is {rpi.get('network_interface')}, expected eth0")

        # Validate OpenSearch credentials placeholders
        opensearch_creds = self.config.get('opensearch_credentials', {})
        validate_env_placeholder(
            opensearch_creds.get('master_user'),
            "OPENSEARCH_MASTER_USER",
            "OPENSEARCH_MASTER_USER",
            "OpenSearch master_user",
        )
        validate_env_placeholder(
            opensearch_creds.get('master_pass'),
            "OPENSEARCH_MASTER_PASS",
            "OPENSEARCH_MASTER_PASS",
            "OpenSearch master_pass",
        )

        # Validate Grafana credentials placeholders
        monitoring_config = self.config.get('monitoring', {})
        validate_env_placeholder(
            monitoring_config.get('grafana_admin_user'),
            "GRAFANA_ADMIN_USER",
            "GRAFANA_ADMIN_USER",
            "Grafana admin user",
        )
        validate_env_placeholder(
            monitoring_config.get('grafana_admin_password'),
            "GRAFANA_ADMIN_PASSWORD",
            "GRAFANA_ADMIN_PASSWORD",
            "Grafana admin password",
        )

        # Validate Git credentials placeholders
        git_config = self.config.get('git', {})
        validate_env_placeholder(
            git_config.get('author_name'),
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_NAME",
            "Git author name",
        )
        validate_env_placeholder(
            git_config.get('author_email'),
            "GIT_AUTHOR_EMAIL",
            "GIT_AUTHOR_EMAIL",
            "Git author email",
        )
        validate_env_placeholder(
            git_config.get('committer_name'),
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_NAME",
            "Git committer name",
        )
        validate_env_placeholder(
            git_config.get('committer_email'),
            "GIT_COMMITTER_EMAIL",
            "GIT_COMMITTER_EMAIL",
            "Git committer email",
        )
        
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
        """Get AWS OpenSearch configuration, loading IAM user ARN from environment if placeholder is used."""
        aws = self.get_section('aws')
        
        aws['iam_user_arn'] = resolve_env_placeholder(
            aws.get('iam_user_arn'),
            "IAM_USER_ARN",
            "IAM_USER_ARN",
            "IAM user ARN",
        )

        return {
            'region': aws.get('region', 'us-east-1'),
            'profile': aws.get('profile', 'moi33'),
            'domain_name': aws.get('opensearch_domain'),
            'endpoint': aws.get('opensearch_endpoint'),
            'iam_user_arn': aws.get('iam_user_arn'),
            'index_prefix': aws.get('index_prefix', 'ids2-logs'),
            'bulk_size': aws.get('bulk_size', 100),
            'bulk_timeout': aws.get('bulk_timeout', 30),
        }
    
    def get_opensearch_credentials(self) -> Dict[str, str]:
        """
        Get OpenSearch master user credentials from environment variables.
        
        Returns:
            Dictionary with 'master_user' and 'master_pass'.
        Raises:
            ValueError: If environment variables are not set.
        """
        creds_config = self.get_section('opensearch_credentials')
        master_user = resolve_env_placeholder(
            creds_config.get('master_user'),
            "OPENSEARCH_MASTER_USER",
            "OPENSEARCH_MASTER_USER",
            "OpenSearch master user",
        )
        master_pass = resolve_env_placeholder(
            creds_config.get('master_pass'),
            "OPENSEARCH_MASTER_PASS",
            "OPENSEARCH_MASTER_PASS",
            "OpenSearch master password",
        )
        
        return {
            'master_user': master_user,
            'master_pass': master_pass
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
        """Get monitoring configuration, loading Grafana credentials from environment if placeholders are used."""
        monitoring = self.get_section('monitoring')
        
        monitoring['grafana_admin_user'] = resolve_env_placeholder(
            monitoring.get('grafana_admin_user'),
            "GRAFANA_ADMIN_USER",
            "GRAFANA_ADMIN_USER",
            "Grafana admin user",
            required=False,
        )
        monitoring['grafana_admin_password'] = resolve_env_placeholder(
            monitoring.get('grafana_admin_password'),
            "GRAFANA_ADMIN_PASSWORD",
            "GRAFANA_ADMIN_PASSWORD",
            "Grafana admin password",
            required=False,
        )

        return monitoring
    
    def get_git_config(self) -> Dict[str, Any]:
        """Get Git workflow configuration, loading user info from environment if placeholders are used."""
        git_config = self.get_section('git')

        git_config['author_name'] = resolve_env_placeholder(
            git_config.get('author_name'),
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_NAME",
            "Git author name",
            required=False,
        )
        git_config['author_email'] = resolve_env_placeholder(
            git_config.get('author_email'),
            "GIT_AUTHOR_EMAIL",
            "GIT_AUTHOR_EMAIL",
            "Git author email",
            required=False,
        )
        git_config['committer_name'] = resolve_env_placeholder(
            git_config.get('committer_name'),
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_NAME",
            "Git committer name",
            required=False,
        )
        git_config['committer_email'] = resolve_env_placeholder(
            git_config.get('committer_email'),
            "GIT_COMMITTER_EMAIL",
            "GIT_COMMITTER_EMAIL",
            "Git committer email",
            required=False,
        )

        return git_config
    
    def get_opensearch_creation_config(self) -> Dict[str, Any]:
        """Get OpenSearch domain creation configuration."""
        return self.get_section('opensearch_creation')

    def get_raspberry_pi_remote_config(self) -> Dict[str, Any]:
        """Get Raspberry Pi remote configuration."""
        return self.get_section('raspberry_pi_remote')

    def get_testing_config(self) -> Dict[str, Any]:
        """Get testing configuration."""
        return self.get_section('testing')

    def get_features_config(self) -> Dict[str, Any]:
        """Get feature flags configuration."""
        return self.get_section('features')

    def get_timeouts_config(self) -> Dict[str, Any]:
        """Get timeouts configuration."""
        return self.get_section('timeouts')

    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration."""
        return self.get_section('retry')

    def get_health_checks_config(self) -> Dict[str, Any]:
        """Get health checks configuration."""
        return self.get_section('health_checks')

    def reload(self) -> None:
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        self._validate_config()
    
    def __repr__(self) -> str:
        return f"ConfigManager(config_path={self.config_path})"

    def set_aws_opensearch_endpoint(self, endpoint: str) -> None:
        """
        Set the AWS OpenSearch endpoint in the configuration and save it.

        Args:
            endpoint: The new OpenSearch endpoint URL.
        """
        if 'aws' not in self.config:
            self.config['aws'] = {}
        self.config['aws']['opensearch_endpoint'] = endpoint
        self._save_config()
        logger.info(f"OpenSearch endpoint updated to {endpoint} in {self.config_path}")

    def _save_config(self) -> None:
        """Save the current configuration to the YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
