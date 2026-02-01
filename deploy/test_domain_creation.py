#!/usr/bin/env python3
"""
Test script to create OpenSearch domain without interactive prompts
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

def create_domain():
    """Create OpenSearch domain"""
    # Load configuration
    try:
        config_manager = ConfigManager()
        aws_config = config_manager.get_aws_config()
        opensearch_credentials = config_manager.get_opensearch_credentials()
        opensearch_creation_config = config_manager.get_section('opensearch_creation')
        timeouts_config = config_manager.get_section('timeouts')
        health_checks_config = config_manager.get_section('health_checks')
        
        aws_profile = aws_config['profile']
        aws_region = aws_config['region']
        domain_name = aws_config['domain_name']
        master_username = opensearch_credentials['master_user']
        master_password = opensearch_credentials['master_pass']
        
        engine_version = opensearch_creation_config.get('engine_version', 'OpenSearch_2.11')
        instance_type = opensearch_creation_config.get('instance_type', 't3.small.search')
        instance_count = opensearch_creation_config.get('instance_count', 1)
        ebs_volume_type = opensearch_creation_config.get('ebs_volume_type', 'gp3')
        ebs_volume_size = opensearch_creation_config.get('ebs_volume_size', 10)
        
        max_wait_minutes = timeouts_config.get('aws_domain_check', 20)
        check_interval_seconds = health_checks_config.get('resource_check_interval', 15)
        
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

    print("Initializing AWS session...")
    session = boto3.Session(
        profile_name=aws_profile,
        region_name=aws_region
    )
    client = session.client('opensearch')
    
    print(f"\nCreating domain: {domain_name}")
    print("Configuration:")
    print(f"  - No resource policy (completely open)")
    print(f"  - FGAC only ({master_username}/{master_password})")
    print(f"  - Instance: {instance_type}")
    
    try:
        # Check if exists
        try:
            response = client.describe_domain(DomainName=domain_name)
            print(f"\n✅ Domain already exists!")
            endpoint = response['DomainStatus'].get('Endpoint', 'N/A')
            print(f"   Endpoint: https://{endpoint}")
            return endpoint
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise
        
        # Create domain
        print("\nCreating new domain...")
        response = client.create_domain(
            DomainName=domain_name,
            EngineVersion=engine_version,
            ClusterConfig={
                'InstanceType': instance_type,
                'InstanceCount': instance_count,
                'DedicatedMasterEnabled': False,
                'ZoneAwarenessEnabled': False,
            },
            EBSOptions={
                'EBSEnabled': True,
                'VolumeType': ebs_volume_type,
                'VolumeSize': ebs_volume_size,
            },
            # NO AccessPolicies - completely open
            AdvancedSecurityOptions={
                'Enabled': True,
                'InternalUserDatabaseEnabled': True,
                'MasterUserOptions': {
                    'MasterUserName': master_username,
                    'MasterUserPassword': master_password,
                }
            },
            NodeToNodeEncryptionOptions={'Enabled': True},
            EncryptionAtRestOptions={'Enabled': True},
            DomainEndpointOptions={
                'EnforceHTTPS': True,
                'TLSSecurityPolicy': 'Policy-Min-TLS-1-2-2019-07',
            }
        )
        
        print("✅ Domain creation initiated")
        
        # Wait for domain
        print("\n⏳ Waiting for domain to become active (10-15 minutes)...")
        max_iterations = (max_wait_minutes * 60) // check_interval_seconds
        
        for i in range(max_iterations):
            time.sleep(check_interval_seconds)
            
            response = client.describe_domain(DomainName=domain_name)
            domain_status = response['DomainStatus']
            processing = domain_status.get('Processing', True)
            
            progress = int((i + 1) / max_iterations * 100)
            print(f"   Progress: {progress}% (checking...)", end='\r')
            
            if not processing:
                endpoint = domain_status.get('Endpoint', 'N/A')
                print(f"\n\n✅ Domain is active!")
                print(f"   Endpoint: https://{endpoint}")
                return endpoint
        
        print("\n❌ Timeout waiting for domain")
        return None
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    endpoint = create_domain()
    if endpoint:
        print(f"\n{'='*80}")
        print("Domain Ready!")
        print(f"{'='*80}")
        print(f"\nEndpoint: https://{endpoint}")
        
        # Load credentials for display
        try:
            config_manager = ConfigManager()
            opensearch_credentials = config_manager.get_opensearch_credentials()
            master_username = opensearch_credentials['master_user']
            master_password = opensearch_credentials['master_pass']
        except Exception as e:
            print(f"❌ Failed to load credentials for display: {e}")
            master_username = "admin" # Fallback
            master_password = "password" # Fallback

        print(f"Username: {master_username}")
        print(f"Password: {master_password}")
        print(f"\nTest with:")
        print(f"  curl -u {master_username}:{master_password} https://{endpoint}/")
        sys.exit(0)
    else:
        sys.exit(1)
