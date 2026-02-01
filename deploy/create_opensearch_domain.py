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

# ============================================================================
# CONFIGURATION - ALL VARIABLES IN ONE PLACE
# ============================================================================

CONFIG = {
    # AWS Configuration
    'aws_profile': 'moi33',
    'aws_region': 'us-east-1',
    
    # OpenSearch Domain Configuration
    'domain_name': 'ids2-soc-domain',
    'engine_version': 'OpenSearch_2.11',
    
    # Instance Configuration
    'instance_type': 't3.small.search',
    'instance_count': 1,
    'ebs_volume_type': 'gp3',
    'ebs_volume_size': 10,  # GB
    
    # Security Configuration
    'master_username': 'admin',
    'master_password': 'Admin123!',  # CHANGE THIS IN PRODUCTION!
    
    # Network Configuration
    'allowed_ip': '192.168.178.66/32',  # Raspberry Pi IP
    
    # Timeouts
    'max_wait_minutes': 20,
    'check_interval_seconds': 15,
}

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
    
    def __init__(self, config):
        self.config = config
        
        # Initialize boto3 session
        try:
            self.session = boto3.Session(
                profile_name=config['aws_profile'],
                region_name=config['aws_region']
            )
            self.client = self.session.client('opensearch')
            print(f"✅ AWS session initialized (profile: {config['aws_profile']}, region: {config['aws_region']})")
        except Exception as e:
            print(f"❌ Failed to initialize AWS session: {e}")
            sys.exit(1)
    
    def check_domain_exists(self):
        """Check if domain already exists"""
        try:
            response = self.client.describe_domain(
                DomainName=self.config['domain_name']
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
        print(f"Creating OpenSearch Domain: {self.config['domain_name']}")
        print(f"{'='*80}\n")
        
        # Build access policy
        access_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "es:*",
                    "Resource": f"arn:aws:es:{self.config['aws_region']}:*:domain/{self.config['domain_name']}/*",
                }
            ]
        }
        
        # Create domain
        try:
            response = self.client.create_domain(
                DomainName=self.config['domain_name'],
                EngineVersion=self.config['engine_version'],
                ClusterConfig={
                    'InstanceType': self.config['instance_type'],
                    'InstanceCount': self.config['instance_count'],
                    'DedicatedMasterEnabled': False,
                    'ZoneAwarenessEnabled': False,
                },
                EBSOptions={
                    'EBSEnabled': True,
                    'VolumeType': self.config['ebs_volume_type'],
                    'VolumeSize': self.config['ebs_volume_size'],
                },
                AccessPolicies=json.dumps(access_policy),
                AdvancedSecurityOptions={
                    'Enabled': True,
                    'InternalUserDatabaseEnabled': True,
                    'MasterUserOptions': {
                        'MasterUserName': self.config['master_username'],
                        'MasterUserPassword': self.config['master_password'],
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
        
        max_iterations = (self.config['max_wait_minutes'] * 60) // self.config['check_interval_seconds']
        progress = ProgressBar(max_iterations, prefix='Creating domain:', length=50)
        
        for i in range(max_iterations):
            try:
                response = self.client.describe_domain(
                    DomainName=self.config['domain_name']
                )
                
                domain_status = response['DomainStatus']
                processing = domain_status.get('Processing', True)
                
                # Update progress bar
                progress.update(i + 1)
                
                if not processing:
                    progress.finish()
                    print(f"\n✅ Domain is now active!")
                    return domain_status
                
                time.sleep(self.config['check_interval_seconds'])
                
            except ClientError as e:
                print(f"\n❌ Error checking domain status: {e}")
                sys.exit(1)
        
        print(f"\n❌ Timeout waiting for domain to become active")
        print(f"   Check status with: aws opensearch describe-domain --domain-name {self.config['domain_name']}")
        sys.exit(1)
    
    def get_domain_info(self):
        """Get domain information"""
        try:
            response = self.client.describe_domain(
                DomainName=self.config['domain_name']
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
        print(f"   Name:           {self.config['domain_name']}")
        print(f"   Endpoint:       https://{endpoint}")
        print(f"   ARN:            {arn}")
        print(f"   Region:         {self.config['aws_region']}")
        print(f"   Engine:         {self.config['engine_version']}")
        print(f"   Instance:       {self.config['instance_type']}")
        print(f"   Master User:    {self.config['master_username']}")
        print(f"   Master Pass:    {self.config['master_password']}")
        
        print(f"\n🔒 Access Configuration:")
        print(f"   Type:           PUBLIC")
        print(f"   Allowed IP:     {self.config['allowed_ip']}")
        print(f"   HTTPS:          Enforced")
        print(f"   TLS:            1.2+")
        
        print(f"\n📝 Next Steps:")
        print(f"   1. Update config.yaml:")
        print(f"      opensearch_endpoint: \"https://{endpoint}\"")
        print(f"\n   2. Test connection from Raspberry Pi:")
        print(f"      curl -u {self.config['master_username']}:{self.config['master_password']} https://{endpoint}")
        print(f"\n   3. Access OpenSearch Dashboards:")
        print(f"      https://{endpoint}/_dashboards")
        
        print(f"\n{'='*80}\n")
        
        return endpoint

# ============================================================================
# CONFIG FILE UPDATER
# ============================================================================

def update_config_file(endpoint):
    """Update config.yaml with OpenSearch endpoint"""
    config_file = 'config.yaml'
    
    try:
        # Read current config
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Update endpoint
        import re
        pattern = r'opensearch_endpoint:\s*"[^"]*"'
        replacement = f'opensearch_endpoint: "https://{endpoint}"'
        
        if re.search(pattern, content):
            updated_content = re.sub(pattern, replacement, content)
        else:
            # If not found, add it
            pattern = r'(opensearch_domain:\s*"[^"]*")'
            replacement = f'\\1\n  opensearch_endpoint: "https://{endpoint}"'
            updated_content = re.sub(pattern, replacement, content)
        
        # Write updated config
        with open(config_file, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated {config_file} with endpoint: https://{endpoint}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update config file: {e}")
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow"""
    print(f"\n{'='*80}")
    print(f"IDS2 SOC Pipeline - OpenSearch Domain Creation")
    print(f"{'='*80}\n")
    
    # Display configuration
    print(f"📋 Configuration:")
    print(f"   AWS Profile:    {CONFIG['aws_profile']}")
    print(f"   AWS Region:     {CONFIG['aws_region']}")
    print(f"   Domain Name:    {CONFIG['domain_name']}")
    print(f"   Instance Type:  {CONFIG['instance_type']}")
    print(f"   EBS Volume:     {CONFIG['ebs_volume_size']}GB")
    print(f"   Allowed IP:     {CONFIG['allowed_ip']}")
    print(f"   Access Type:    PUBLIC (Internet accessible)")
    
    print(f"\n⚠️  WARNING: This will create a PUBLIC OpenSearch domain!")
    print(f"   The domain will be accessible from the internet.")
    print(f"   Make sure to use strong credentials and IP restrictions.\n")
    
    # Confirm
    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Aborted")
        sys.exit(0)
    
    # Initialize manager
    manager = OpenSearchDomainManager(CONFIG)
    
    # Check if domain exists
    print(f"\n🔍 Checking if domain already exists...")
    exists, domain_status = manager.check_domain_exists()
    
    if exists:
        print(f"⚠️  Domain '{CONFIG['domain_name']}' already exists")
        endpoint = domain_status.get('Endpoint', 'N/A')
        print(f"   Endpoint: https://{endpoint}")
        
        use_existing = input("\nUse existing domain? (yes/no): ")
        if use_existing.lower() == 'yes':
            manager.display_domain_info(domain_status)
            update_config_file(endpoint)
            return endpoint
        else:
            print("\n❌ Please delete the existing domain first:")
            print(f"   aws opensearch delete-domain --domain-name {CONFIG['domain_name']} --profile {CONFIG['aws_profile']} --region {CONFIG['aws_region']}")
            sys.exit(1)
    
    print(f"✅ Domain does not exist, proceeding with creation")
    
    # Create domain
    domain_status = manager.create_domain()
    
    # Wait for domain to become active
    domain_status = manager.wait_for_domain()
    
    # Display domain info
    endpoint = manager.display_domain_info(domain_status)
    
    # Update config file
    update_config_file(endpoint)
    
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
