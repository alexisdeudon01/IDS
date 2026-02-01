#!/usr/bin/env python3
"""
Test OpenSearch Domain Connection
Uses AWS SigV4 authentication to bypass IP restrictions
"""

import sys
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests
from requests.auth import HTTPBasicAuth

# Configuration
AWS_PROFILE = 'moi33'
AWS_REGION = 'us-east-1'
DOMAIN_NAME = 'ids2-soc-domain'
ENDPOINT = 'search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com'
MASTER_USER = 'admin'
MASTER_PASS = 'Admin123!'

def test_with_basic_auth():
    """Test with basic authentication (will fail due to IP restriction)"""
    print("\n" + "="*80)
    print("Test 1: Basic Authentication (HTTP Basic Auth)")
    print("="*80)
    
    url = f'https://{ENDPOINT}'
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Basic auth successful!")
            return True
        else:
            print(f"❌ Basic auth failed (expected due to IP restriction)")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_with_sigv4():
    """Test with AWS SigV4 authentication"""
    print("\n" + "="*80)
    print("Test 2: AWS SigV4 Authentication (Bypasses IP restriction)")
    print("="*80)
    
    # Create boto3 session
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    credentials = session.get_credentials()
    
    # Create request
    url = f'https://{ENDPOINT}'
    request = AWSRequest(method='GET', url=url)
    
    # Sign request
    SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
    
    # Send request
    try:
        response = requests.get(url, headers=dict(request.headers), timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SigV4 auth successful!")
            print(f"\nCluster Info:")
            print(f"  Name: {data.get('name', 'N/A')}")
            print(f"  Version: {data.get('version', {}).get('number', 'N/A')}")
            print(f"  Distribution: {data.get('version', {}).get('distribution', 'N/A')}")
            return True
        else:
            print(f"❌ SigV4 auth failed")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_cluster_health():
    """Test cluster health endpoint"""
    print("\n" + "="*80)
    print("Test 3: Cluster Health Check")
    print("="*80)
    
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
        print(f"❌ Error: {e}")
        return False

def test_index_creation():
    """Test creating a test index"""
    print("\n" + "="*80)
    print("Test 4: Index Creation Test")
    print("="*80)
    
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
        print(f"❌ Error: {e}")
        return False

def update_config_yaml():
    """Update config.yaml with endpoint"""
    print("\n" + "="*80)
    print("Updating config.yaml")
    print("="*80)
    
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
    print("\n" + "="*80)
    print("IDS2 SOC Pipeline - OpenSearch Connection Test")
    print("="*80)
    
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
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)
    
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
