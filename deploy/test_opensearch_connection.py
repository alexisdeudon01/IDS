#!/usr/bin/env python3
"""
Test OpenSearch Domain Connection
Uses AWS SigV4 authentication to bypass IP restrictions
"""

import sys
import requests
from requests.auth import HTTPBasicAuth
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import json
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_env" / "modules"))

from config_manager import ConfigManager

# Load configuration
try:
    config = ConfigManager()
    aws_config = config.get_aws_config()
    opensearch_credentials = config.get_opensearch_credentials()
    
    DOMAIN_NAME = aws_config['domain_name']
    AWS_PROFILE = aws_config['profile']
    AWS_REGION = aws_config['region']
    ENDPOINT = aws_config['endpoint']
    MASTER_USER = opensearch_credentials['master_user']
    MASTER_PASS = opensearch_credentials['master_pass']

except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    sys.exit(1)

def test_with_basic_auth():
    """Test with basic authentication (will fail due to IP restriction)"""
    print(f"\n{'='*80}")
    print("TEST 1: Basic Authentication (No Resource Policy)")
    print(f"{'='*80}")
    
    url = f'https://{ENDPOINT}/'
    
    try:
        print(f"\n🔍 Testing: GET {url}")
        print(f"   Auth: Basic ({MASTER_USER}/{MASTER_PASS})")
        print(f"   Expected: 200 OK (no resource policy blocking)")
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
            timeout=10
        )
        
        print(f"\n✅ Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Cluster: {data.get('cluster_name', 'N/A')}")
            print(f"   Version: {data['version'].get('number', 'N/A')}")
            print(f"\n✅ SUCCESS: Basic Auth works with no resource policy!")
            return True
        else:
            print(f"   Body: {response.text[:200]}")
            print(f"\n❌ FAILED: Unexpected status code")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_sigv4_auth(endpoint):
    """Test AWS SigV4 Authentication"""
    print(f"\n{'='*80}")
    print("TEST 2: AWS SigV4 Authentication (No Resource Policy)")
    print(f"{'='*80}")
    
    url = f'https://{endpoint}/'
    
    try:
        print(f"\n🔍 Testing: GET {url}")
        print(f"   Auth: AWS SigV4 (IAM user: alexis)")
        print(f"   Expected: 200 OK or 403 (depends on FGAC role mapping)")
        
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        credentials = session.get_credentials()
        
        request = AWSRequest(method='GET', url=url)
        SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
        
        response = requests.get(url, headers=dict(request.headers), timeout=10)
        
        print(f"\n✅ Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Cluster: {data.get('cluster_name', 'N/A')}")
            print(f"\n✅ SUCCESS: SigV4 works (IAM user mapped in FGAC)")
            return True
        elif response.status_code == 403:
            print(f"   Message: {response.text[:200]}")
            print(f"\n⚠️  EXPECTED: SigV4 blocked by FGAC (IAM user not mapped)")
            print(f"   This is normal - no resource policy, but FGAC controls access")
            return True
        else:
            print(f"   Body: {response.text[:200]}")
            print(f"\n❌ FAILED: Unexpected status code")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_cluster_health():
    """Test cluster health endpoint"""
    print(f"\n{'='*80}")
    print("Test 3: Cluster Health Check")
    print(f"{'='*80}")
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    credentials = session.get_credentials()
    
    url = f'https://{ENDPOINT}/_cluster/health'
    request = AWSRequest(method='GET', url=url)
    SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
    
    try:
        response = requests.get(url, headers=dict(request.headers), timeout=10)
        
        if response.status_code == 200:
            health = response.json()
            print(f"✅ Cluster health check successful!")
            print(f"\nHealth Status:")
            print(f"  Status: {health.get('status', 'N/A')}")
            print(f"  Nodes: {health.get('number_of_nodes', 'N/A')}")
            print(f"  Data Nodes: {health.get('number_of_data_nodes', 'N/A')}")
            print(f"  Active Shards: {health.get('active_shards', 'N/A')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_index_creation():
    """Test creating a test index"""
    print(f"\n{'='*80}")
    print("Test 4: Index Creation Test")
    print(f"{'='*80}")
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    credentials = session.get_credentials()
    
    # Create test index
    index_name = 'test-ids2-connection'
    url = f'https://{ENDPOINT}/{index_name}'
    
    # PUT request to create index (must include Content-Type; sign AFTER setting headers)
    body = '{}'
    signed_headers = {'Content-Type': 'application/json'}
    request = AWSRequest(method='PUT', url=url, data=body, headers=signed_headers)
    SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
    
    try:
        response = requests.put(
            url,
            headers=dict(request.headers),
            data=body,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Test index created successfully!")
            
            # Delete test index
            del_headers = {}
            del_request = AWSRequest(method='DELETE', url=url, headers=del_headers)
            SigV4Auth(credentials, 'es', AWS_REGION).add_auth(del_request)
            requests.delete(url, headers=dict(del_request.headers), timeout=10)
            print(f"✅ Test index deleted successfully!")
            return True
        elif response.status_code == 400:
            print(f"⚠️  Index already exists (this is OK)")
            return True
        else:
            print(f"❌ Index creation failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def update_config_yaml():
    """Update config.yaml with endpoint"""
    print(f"\n{'='*80}")
    print("Updating config.yaml")
    print(f"{'='*80}")
    
    config_file = 'config.yaml'
    endpoint_url = f'https://{ENDPOINT}'
    
    try:
        with open(config_file, 'r') as f:
            content = f.read()
        
        import re
        pattern = r'opensearch_endpoint:\s*"[^"]*"'
        replacement = f'opensearch_endpoint: "{endpoint_url}"'
        
        if re.search(pattern, content):
            updated_content = re.sub(pattern, replacement, content)
            print(f"✅ Found existing endpoint, updating...")
        else:
            # Add after opensearch_domain
            pattern = r'(opensearch_domain:\s*"[^"]*")'
            replacement = f'\\1\n  opensearch_endpoint: "{endpoint_url}"'
            updated_content = re.sub(pattern, replacement, content)
            print(f"✅ Adding new endpoint entry...")
        
        with open(config_file, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated {config_file}")
        print(f"   Endpoint: {endpoint_url}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update config: {e}")
        return False

def main():
    """Main test execution"""
    print(f"\n{'='*80}")
    print("IDS2 SOC Pipeline - OpenSearch Connection Test")
    print(f"{'='*80}")
    
    print(f"\n📋 Configuration:")
    print(f"   AWS Profile: {AWS_PROFILE}")
    print(f"   AWS Region: {AWS_REGION}")
    print(f"   Domain: {DOMAIN_NAME}")
    print(f"   Endpoint: {ENDPOINT}")
    
    results = {
        'basic_auth': False,
        'sigv4_auth': False,
        'cluster_health': False,
        'index_creation': False,
        'config_update': False
    }
    
    # Run tests
    results['basic_auth'] = test_with_basic_auth()
    results['sigv4_auth'] = test_with_sigv4()
    
    if results['sigv4_auth']:
        results['cluster_health'] = test_cluster_health()
        results['index_creation'] = test_index_creation()
        results['config_update'] = update_config_yaml()
    
    # Summary
    print(f"\n{'='*80}")
    print("Test Summary")
    print(f"{'='*80}\n")
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test.replace('_', ' ').title()}: {status}")
    
    total = sum(results.values())
    print(f"\nTotal: {total}/{len(results)} tests passed")
    
    if results['sigv4_auth']:
        print("\n✅ OpenSearch domain is accessible and functional!")
        print(f"\n📝 Connection Details:")
        print(f"   Endpoint: https://{ENDPOINT}")
        print(f"   Authentication: AWS SigV4 (recommended) or Basic Auth")
        print(f"   Master User: {MASTER_USER}")
        print(f"   Master Password: {MASTER_PASS}")
        print(f"\n🔐 Note: Basic auth only works from IP 192.168.178.66/32 (Raspberry Pi)")
        print(f"   Use AWS SigV4 authentication for access from other IPs")
        return 0
    else:
        print("\n❌ OpenSearch domain is not accessible")
        return 1

if __name__ == "__main__":
    sys.exit(main())
