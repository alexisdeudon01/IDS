#!/usr/bin/env python3
"""
Test OpenSearch domain with NO resource policy
Tests both Basic Auth and AWS SigV4 authentication
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
    MASTER_USER = opensearch_credentials['master_user']
    MASTER_PASS = opensearch_credentials['master_pass']

except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    sys.exit(1)

def get_endpoint():
    """Get domain endpoint"""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    client = session.client('opensearch')
    
    try:
        response = client.describe_domain(DomainName=DOMAIN_NAME)
        endpoint = response['DomainStatus'].get('Endpoint')
        processing = response['DomainStatus'].get('Processing', True)
        
        if not endpoint:
            print("❌ Domain endpoint not available yet (still creating)")
            return None, True
        
        if processing:
            print(f"⏳ Domain is still processing...")
            print(f"   Endpoint: https://{endpoint}")
            print(f"   Will test anyway...")
        
        return endpoint, processing
        
    except Exception as e:
        print(f"❌ Error getting endpoint: {e}")
        return None, True

def test_basic_auth(endpoint):
    """Test Basic Authentication (username/password)"""
    print(f"\n{'='*80}")
    print("TEST 1: Basic Authentication (No Resource Policy)")
    print(f"{'='*80}")
    
    url = f'https://{endpoint}/'
    
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

def test_create_index(endpoint):
    """Test creating an index"""
    print(f"\n{'='*80}")
    print("TEST 3: Create Index (No Resource Policy)")
    print(f"{'='*80}")
    
    url = f'https://{endpoint}/test-no-policy-index'
    
    try:
        print(f"\n🔍 Testing: PUT {url}")
        print(f"   Auth: Basic ({MASTER_USER}/{MASTER_PASS})")
        print(f"   Expected: 200 OK")
        
        response = requests.put(
            url,
            auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
            headers={'Content-Type': 'application/json'},
            json={
                'settings': {
                    'number_of_shards': 1,
                    'number_of_replicas': 0
                }
            },
            timeout=10
        )
        
        print(f"\n✅ Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            print(f"\n✅ SUCCESS: Index created successfully!")
            
            # Clean up
            print(f"\n🧹 Cleaning up...")
            delete_response = requests.delete(
                url,
                auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
                timeout=10
            )
            print(f"   Deleted: {delete_response.status_code}")
            return True
        else:
            print(f"   Body: {response.text[:200]}")
            print(f"\n❌ FAILED: Could not create index")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def verify_no_policy(endpoint):
    """Verify the domain has no resource policy"""
    print(f"\n{'='*80}")
    print("VERIFICATION: Check Access Policy Configuration")
    print(f"{'='*80}")
    
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        client = session.client('opensearch')
        
        response = client.describe_domain(DomainName=DOMAIN_NAME)
        access_policy = response['DomainStatus'].get('AccessPolicies', '')
        
        print(f"\n📋 Access Policy: '{access_policy}'")
        
        if access_policy == '' or access_policy == '{}':
            print(f"\n✅ CONFIRMED: Domain has NO resource policy")
            print(f"   - No IAM restrictions")
            print(f"   - No IP restrictions")
            print(f"   - Security relies on FGAC only")
            return True
        else:
            print(f"\n❌ WARNING: Domain has a resource policy:")
            print(f"   {access_policy}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def main():
    """Run all tests"""
    print(f"\n{'='*80}")
    print("OpenSearch Domain - No Resource Policy Tests")
    print(f"{'='*80}")
    print(f"\nDomain: {DOMAIN_NAME}")
    print(f"Region: {AWS_REGION}")
    print(f"Profile: {AWS_PROFILE}")
    
    # Get endpoint
    endpoint, processing = get_endpoint()
    if not endpoint:
        print(f"\n❌ Cannot proceed - domain not ready")
        sys.exit(1)
    
    print(f"\nEndpoint: https://{endpoint}")
    
    # Run tests
    results = []
    
    results.append(("Access Policy Verification", verify_no_policy(endpoint)))
    results.append(("Basic Auth Test", test_basic_auth(endpoint)))
    results.append(("SigV4 Auth Test", test_sigv4_auth(endpoint)))
    results.append(("Create Index Test", test_create_index(endpoint)))
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("✅ All tests passed! Domain configured correctly with no resource policy.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Review output above.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
