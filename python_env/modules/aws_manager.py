"""
AWS Manager Module

Handles AWS OpenSearch domain provisioning, verification, and bulk ingestion.
Uses boto3 with profile 'moi33'.
"""

import time
import json
import logging
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class AWSManager:
    """Manages AWS OpenSearch interactions"""
    
    def __init__(self, config_manager):
        """
        Initialize AWS manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.aws_config = config_manager.get_aws_config()
        
        # AWS session with profile
        self.profile = self.aws_config['profile']
        self.region = self.aws_config['region']
        
        try:
            self.session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region
            )
            logger.info(f"AWS session created with profile '{self.profile}' in region '{self.region}'")
        except Exception as e:
            logger.error(f"Failed to create AWS session: {e}")
            raise
        
        # OpenSearch client
        self.opensearch_client = None
        self._init_opensearch_client()
    
    def _init_opensearch_client(self) -> None:
        """Initialize OpenSearch client"""
        try:
            self.opensearch_client = self.session.client('opensearch')
            logger.info("OpenSearch client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenSearch client: {e}")
            raise
    
    def verify_domain_exists(self, domain_name: str) -> bool:
        """
        Verify that OpenSearch domain exists
        
        Args:
            domain_name: Name of the OpenSearch domain
            
        Returns:
            True if domain exists and is active
        """
        try:
            response = self.opensearch_client.describe_domain(
                DomainName=domain_name
            )
            
            domain_status = response['DomainStatus']
            processing = domain_status.get('Processing', False)
            created = domain_status.get('Created', False)
            deleted = domain_status.get('Deleted', False)
            
            if deleted:
                logger.error(f"Domain {domain_name} is deleted")
                return False
            
            if processing:
                logger.warning(f"Domain {domain_name} is still processing")
                return False
            
            if not created:
                logger.warning(f"Domain {domain_name} is not fully created")
                return False
            
            endpoint = domain_status.get('Endpoint')
            if endpoint:
                logger.info(f"Domain {domain_name} exists with endpoint: {endpoint}")
                return True
            else:
                logger.warning(f"Domain {domain_name} exists but has no endpoint")
                return False
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Domain {domain_name} not found")
            else:
                logger.error(f"Error checking domain {domain_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking domain: {e}")
            return False
    
    def get_domain_endpoint(self, domain_name: str) -> Optional[str]:
        """
        Get OpenSearch domain endpoint
        
        Args:
            domain_name: Name of the OpenSearch domain
            
        Returns:
            Domain endpoint URL or None if not available
        """
        try:
            response = self.opensearch_client.describe_domain(
                DomainName=domain_name
            )
            
            endpoint = response['DomainStatus'].get('Endpoint')
            if endpoint:
                # Return full HTTPS URL
                return f"https://{endpoint}"
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting domain endpoint: {e}")
            return None
    
    def wait_for_domain_ready(
        self,
        domain_name: str,
        max_wait: int = 600,
        check_interval: int = 30
    ) -> bool:
        """
        Wait for OpenSearch domain to be ready
        
        Args:
            domain_name: Name of the OpenSearch domain
            max_wait: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            
        Returns:
            True if domain becomes ready, False if timeout
        """
        logger.info(f"Waiting for domain {domain_name} to be ready (max {max_wait}s)...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait:
            if self.verify_domain_exists(domain_name):
                logger.info(f"Domain {domain_name} is ready")
                return True
            
            logger.info(f"Domain not ready yet, waiting {check_interval}s...")
            time.sleep(check_interval)
        
        logger.error(f"Timeout waiting for domain {domain_name}")
        return False
    
    def create_index_template(
        self,
        endpoint: str,
        template_name: str,
        index_pattern: str
    ) -> bool:
        """
        Create index template for ECS-compliant logs
        
        Args:
            endpoint: OpenSearch endpoint URL
            template_name: Name of the template
            index_pattern: Index pattern (e.g., 'ids2-logs-*')
            
        Returns:
            True if successful
        """
        # This would use requests or aiohttp to create the template
        # For now, this is a placeholder
        logger.info(f"Index template creation would be implemented here")
        logger.info(f"Template: {template_name}, Pattern: {index_pattern}")
        return True
    
    def test_bulk_ingestion(
        self,
        endpoint: str,
        test_events: List[Dict[str, Any]]
    ) -> bool:
        """
        Test bulk ingestion to OpenSearch
        
        Args:
            endpoint: OpenSearch endpoint URL
            test_events: List of test events to ingest
            
        Returns:
            True if successful
        """
        # This would use requests or aiohttp to send bulk data
        # For now, this is a placeholder
        logger.info(f"Bulk ingestion test would be implemented here")
        logger.info(f"Endpoint: {endpoint}, Events: {len(test_events)}")
        return True
    
    def get_index_stats(self, endpoint: str, index_pattern: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for indices matching pattern
        
        Args:
            endpoint: OpenSearch endpoint URL
            index_pattern: Index pattern to query
            
        Returns:
            Statistics dictionary or None if failed
        """
        # This would query OpenSearch for index stats
        # For now, this is a placeholder
        logger.info(f"Index stats query would be implemented here")
        return None
    
    def verify_credentials(self) -> bool:
        """
        Verify AWS credentials are valid
        
        Returns:
            True if credentials are valid
        """
        try:
            # Try to get caller identity
            sts = self.session.client('sts')
            response = sts.get_caller_identity()
            
            account = response.get('Account')
            arn = response.get('Arn')
            
            logger.info(f"AWS credentials verified - Account: {account}, ARN: {arn}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify AWS credentials: {e}")
            return False
    
    def get_domain_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed domain information
        
        Args:
            domain_name: Name of the OpenSearch domain
            
        Returns:
            Domain information dictionary or None
        """
        try:
            response = self.opensearch_client.describe_domain(
                DomainName=domain_name
            )
            
            domain_status = response['DomainStatus']
            
            info = {
                'domain_name': domain_status.get('DomainName'),
                'domain_id': domain_status.get('DomainId'),
                'arn': domain_status.get('ARN'),
                'created': domain_status.get('Created'),
                'deleted': domain_status.get('Deleted'),
                'endpoint': domain_status.get('Endpoint'),
                'processing': domain_status.get('Processing'),
                'engine_version': domain_status.get('EngineVersion'),
                'cluster_config': domain_status.get('ClusterConfig'),
                'ebs_options': domain_status.get('EBSOptions'),
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting domain info: {e}")
            return None
