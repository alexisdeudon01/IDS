#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - AWS OpenSearch Domain Creation Script
Creates a PUBLIC OpenSearch domain with progress tracking
"""

import sys
import time
import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_env" / "modules"))

from config_manager import ConfigManager

# ============================================================================
# PROGRESS BAR
# ============================================================================

class ProgressBar:
    """Simple progress bar for terminal"""
    
    def __init__(self, total, prefix='Progress:', length=50):
        self.total = total
        self.prefix = prefix
        self.length = length
        self.current = 0
    
    def update(self, current):
        """Update progress bar"""
        self.current = current
        percent = 100 * (current / float(self.total))
        filled = int(self.length * current // self.total)
        bar = '█' * filled + '-' * (self.length - filled)
        
        print(f'\r{self.prefix} |{bar}| {percent:.1f}% Complete', end='', flush=True)
        
        if current >= self.total:
            print()  # New line when complete
    
    def finish(self):
        """Mark as complete"""
        self.update(self.total)

# ============================================================================
# OPENSEARCH DOMAIN MANAGER
# ============================================================================

class OpenSearchDomainManager:
    """Manages OpenSearch domain creation and configuration"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
        # Load AWS and OpenSearch configurations
        aws_config = self.config_manager.get_aws_config()
        opensearch_credentials = self.config_manager.get_opensearch_credentials()
        
        self.aws_profile = aws_config['profile']
        self.aws_region = aws_config['region']
        self.domain_name = aws_config['domain_name']
        self.master_username = opensearch_credentials['master_user']
        self.master_password = opensearch_credentials['master_pass']

        # Load domain creation specific configurations (instance type, EBS, etc.)
        # These could be added to config.yaml under a new section like 'opensearch_creation'
        # For now, we'll define them here or get sensible defaults.
        self.engine_version = self.config_manager.get('opensearch_creation.engine_version', 'OpenSearch_2.11')
        self.instance_type = self.config_manager.get('opensearch_creation.instance_type', 't3.small.search')
        self.instance_count = self.config_manager.get('opensearch_creation.instance_count', 1)
        self.ebs_volume_type = self.config_manager.get('opensearch_creation.ebs_volume_type', 'gp3')
        self.ebs_volume_size = self.config_manager.get('opensearch_creation.ebs_volume_size', 10) # GB
        self.max_wait_minutes = self.config_manager.get('timeouts.aws_domain_check', 20) # Use existing timeout
        self.check_interval_seconds = self.config_manager.get('health_checks.resource_check_interval', 15) # Use existing interval

        # Initialize boto3 session
        try:
            self.session = boto3.Session(
                profile_name=self.aws_profile,
                region_name=self.aws_region
            )
            self.client = self.session.client('opensearch')
            print(f"✅ AWS session initialized (profile: {self.aws_profile}, region: {self.aws_region})")
        except Exception as e:
            print(f"❌ Failed to initialize AWS session: {e}")
            sys.exit(1)
    
    def check_domain_exists(self):
        """Check if domain already exists"""
        try:
            response = self.client.describe_domain(
                DomainName=self.domain_name
            )
            return True, response['DomainStatus']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return False, None
            else:
                raise
    
    def create_domain(self):
        """Create OpenSearch domain"""
        print(f"\n{'='*80}")
        print(f"Creating OpenSearch Domain: {self.domain_name}")
        print(f"{'='*80}\n")
        
        # NO ACCESS POLICY - Completely open, relies on FGAC only
        # This allows access from any IP without resource-based restrictions
        
        # Create domain
        try:
            response = self.client.create_domain(
                DomainName=self.domain_name,
                EngineVersion=self.engine_version,
                ClusterConfig={
                    'InstanceType': self.instance_type,
                    'InstanceCount': self.instance_count,
                    'DedicatedMasterEnabled': False,
                    'ZoneAwarenessEnabled': False,
                },
                EBSOptions={
                    'EBSEnabled': True,
                    'VolumeType': self.ebs_volume_type,
                    'VolumeSize': self.ebs_volume_size,
                },
                # NO AccessPolicies parameter - completely open
                AdvancedSecurityOptions={
                    'Enabled': True,
                    'InternalUserDatabaseEnabled': True,
                    'MasterUserOptions': {
                        'MasterUserName': self.master_username,
                        'MasterUserPassword': self.master_password,
                    }
                },
                NodeToNodeEncryptionOptions={'Enabled': True},
                EncryptionAtRestOptions={'Enabled': True},
                DomainEndpointOptions={
                    'EnforceHTTPS': True,
                    'TLSSecurityPolicy': 'Policy-Min-TLS-1-2-2019-07',
                }
            )
            
            print("✅ Domain creation initiated successfully")
            return response['DomainStatus']
            
        except ClientError as e:
            print(f"❌ Failed to create domain: {e}")
            sys.exit(1)
    
    def wait_for_domain(self):
        """Wait for domain to become active with progress bar"""
        print(f"\n⏳ Waiting for domain to become active...")
        print(f"   This typically takes 10-15 minutes. Please wait...\n")
        
        max_iterations = (self.max_wait_minutes * 60) // self.check_interval_seconds
        progress = ProgressBar(max_iterations, prefix='Creating domain:', length=50)
        
        for i in range(max_iterations):
            try:
                response = self.client.describe_domain(
                    DomainName=self.domain_name
                )
                
                domain_status = response['DomainStatus']
                processing = domain_status.get('Processing', True)
                
                # Update progress bar
                progress.update(i + 1)
                
                if not processing:
                    progress.finish()
                    print(f"\n✅ Domain is now active!")
                    return domain_status
                
                time.sleep(self.check_interval_seconds)
                
            except ClientError as e:
                print(f"\n❌ Error checking domain status: {e}")
                sys.exit(1)
        
        print(f"\n❌ Timeout waiting for domain to become active")
        print(f"   Check status with: aws opensearch describe-domain --domain-name {self.domain_name}")
        sys.exit(1)
    
    def get_domain_info(self):
        """Get domain information"""
        try:
            response = self.client.describe_domain(
                DomainName=self.domain_name
            )
            return response['DomainStatus']
        except ClientError as e:
            print(f"❌ Failed to get domain info: {e}")
            return None
    
    def display_domain_info(self, domain_status):
        """Display domain information"""
        endpoint = domain_status.get('Endpoint', 'N/A')
        arn = domain_status.get('ARN', 'N/A')
        
        print(f"\n{'='*80}")
        print(f"OpenSearch Domain Created Successfully!")
        print(f"{'='*80}\n")
        
        print(f"📋 Domain Details:")
        print(f"   Name:           {self.domain_name}")
        print(f"   Endpoint:       https://{endpoint}")
        print(f"   ARN:            {arn}")
        print(f"   Region:         {self.aws_region}")
        print(f"   Engine:         {self.engine_version}")
        print(f"   Instance:       {self.instance_type}")
        print(f"   Master User:    {self.master_username}")
        print(f"   Master Pass:    {self.master_password}")
        
        print(f"\n🔒 Access Configuration:")
        print(f"   Resource Policy: NONE (Completely open)")
        print(f"   Security:       FGAC only (username/password)")
        print(f"   HTTPS:          Enforced")
        print(f"   TLS:            1.2+")
        print(f"   Auth Required:  Yes (admin/{self.master_password})")
        
        print(f"\n📝 Next Steps:")
        print(f"   1. Update config.yaml:")
        print(f"      opensearch_endpoint: \"https://{endpoint}\"")
        print(f"\n   2. Test connection from Raspberry Pi:")
        print(f"      curl -u {self.master_username}:{self.master_password} https://{endpoint}")
        print(f"\n   3. Access OpenSearch Dashboards:")
        print(f"      https://{endpoint}/_dashboards")
        
        print(f"\n{'='*80}\n")
        
        return endpoint

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow"""
    print(f"\n{'='*80}")
    print(f"IDS2 SOC Pipeline - OpenSearch Domain Creation")
    print(f"{'='*80}\n")
    
    # Initialize ConfigManager
    try:
        config_manager = ConfigManager()
        aws_config = config_manager.get_aws_config()
        opensearch_credentials = config_manager.get_opensearch_credentials()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

    # Display configuration
    print(f"📋 Configuration:")
    print(f"   AWS Profile:    {aws_config['profile']}")
    print(f"   AWS Region:     {aws_config['region']}")
    print(f"   Domain Name:    {aws_config['domain_name']}")
    print(f"   Instance Type:  {config_manager.get('opensearch_creation.instance_type', 't3.small.search')}")
    print(f"   EBS Volume:     {config_manager.get('opensearch_creation.ebs_volume_size', 10)}GB")
    print(f"   Access Policy:  OPEN (No IP restrictions)")
    
    print(f"\n⚠️  WARNING: This will create a domain with NO resource policy!")
    print(f"   - Accessible from ANY IP address")
    print(f"   - NO IAM-based access control")
    print(f"   - Security relies ONLY on FGAC (username/password)")
    print(f"   - Make sure to use STRONG credentials!\n")
    
    # Confirm
    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Aborted")
        sys.exit(0)
    
    # Initialize manager
    manager = OpenSearchDomainManager(config_manager)
    
    # Check if domain exists
    print(f"\n🔍 Checking if domain already exists...")
    exists, domain_status = manager.check_domain_exists()
    
    if exists:
        print(f"⚠️  Domain '{manager.domain_name}' already exists")
        endpoint = domain_status.get('Endpoint', 'N/A')
        print(f"   Endpoint: https://{endpoint}")
        
        use_existing = input("\nUse existing domain? (yes/no): ")
        if use_existing.lower() == 'yes':
            manager.display_domain_info(domain_status)
            config_manager.set_aws_opensearch_endpoint(f"https://{endpoint}")
            return endpoint
        else:
            print("\n❌ Please delete the existing domain first:")
            print(f"   aws opensearch delete-domain --domain-name {manager.domain_name} --profile {manager.aws_profile} --region {manager.aws_region}")
            sys.exit(1)
    
    print(f"✅ Domain does not exist, proceeding with creation")
    
    # Create domain
    domain_status = manager.create_domain()
    
    # Wait for domain to become active
    domain_status = manager.wait_for_domain()
    
    # Display domain info
    endpoint = manager.display_domain_info(domain_status)
    
    # Update config file
    config_manager.set_aws_opensearch_endpoint(f"https://{endpoint}")
    
    print(f"✅ OpenSearch domain creation complete!")
    print(f"\n🚀 Ready to proceed with testing on Raspberry Pi\n")
    
    return endpoint

if __name__ == "__main__":
    try:
        endpoint = main()
        sys.exit(0)
    except KeyboardInterrupt:
        print(f"\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
