#!/usr/bin/env python3
"""
Configure OpenSearch Fine-Grained Access Control
Maps IAM user to all_access role using master credentials
"""

import sys
import json
import requests
from requests.auth import HTTPBasicAuth

# Configuration
ENDPOINT = 'search-ids2-soc-domain-7p7ddhpiegpwgtk77rn7xn53v4.us-east-1.es.amazonaws.com'
MASTER_USER = 'admin'
MASTER_PASS = 'Admin123!'
IAM_USER_ARN = 'arn:aws:iam::211125764416:user/alexis'

def map_iam_user_to_role():
    """Map IAM user to all_access role"""
    print("\n" + "="*80)
    print("Mapping IAM User to all_access Role")
    print("="*80)
    
    url = f'https://{ENDPOINT}/_plugins/_security/api/rolesmapping/all_access'
    
    # Get current role mapping
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
            timeout=10
        )
        
        if response.status_code == 200:
            current_mapping = response.json()
            print(f"✅ Retrieved current role mapping")
            print(f"Current mapping: {json.dumps(current_mapping, indent=2)}")
        else:
            print(f"⚠️  Could not retrieve current mapping: {response.status_code}")
            current_mapping = {'all_access': {}}
            
    except Exception as e:
        print(f"⚠️  Error retrieving mapping: {e}")
        current_mapping = {'all_access': {}}
    
    # Update role mapping to include IAM user
    role_mapping = current_mapping.get('all_access', {})
    
    # Ensure backend_roles exists
    if 'backend_roles' not in role_mapping:
        role_mapping['backend_roles'] = []
    
    # Add IAM user ARN if not already present
    if IAM_USER_ARN not in role_mapping['backend_roles']:
        role_mapping['backend_roles'].append(IAM_USER_ARN)
        print(f"✅ Adding IAM user to backend_roles: {IAM_USER_ARN}")
    else:
        print(f"ℹ️  IAM user already in backend_roles")
    
    # Ensure users exists (for master user)
    if 'users' not in role_mapping:
        role_mapping['users'] = [MASTER_USER]
    elif MASTER_USER not in role_mapping['users']:
        role_mapping['users'].append(MASTER_USER)
    
    # Update role mapping
    try:
        response = requests.put(
            url,
            auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS),
            json=role_mapping,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Successfully updated role mapping!")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"❌ Failed to update role mapping: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating role mapping: {e}")
        return False

def verify_access():
    """Verify IAM user can now access OpenSearch"""
    print("\n" + "="*80)
    print("Verifying IAM User Access")
    print("="*80)
    
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    session = boto3.Session(profile_name='moi33', region_name='us-east-1')
    credentials = session.get_credentials()
    
    url = f'https://{ENDPOINT}'
    request = AWSRequest(method='GET', url=url)
    SigV4Auth(credentials, 'es', 'us-east-1').add_auth(request)
    
    try:
        response = requests.get(url, headers=dict(request.headers), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ IAM user access verified!")
            print(f"\nCluster Info:")
            print(f"  Name: {data.get('name', 'N/A')}")
            print(f"  Version: {data.get('version', {}).get('number', 'N/A')}")
            return True
        else:
            print(f"❌ Access verification failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying access: {e}")
        return False

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("IDS2 SOC Pipeline - Configure OpenSearch Access")
    print("="*80)
    
    print(f"\n📋 Configuration:")
    print(f"   Endpoint: {ENDPOINT}")
    print(f"   Master User: {MASTER_USER}")
    print(f"   IAM User ARN: {IAM_USER_ARN}")
    
    # Map IAM user to role
    if not map_iam_user_to_role():
        print("\n❌ Failed to configure access")
        return 1
    
    # Wait a moment for changes to propagate
    print("\n⏳ Waiting for changes to propagate...")
    import time
    time.sleep(5)
    
    # Verify access
    if verify_access():
        print("\n✅ OpenSearch access configured successfully!")
        print(f"\n📝 IAM user '{IAM_USER_ARN}' now has full access to the domain")
        return 0
    else:
        print("\n⚠️  Access configuration completed but verification failed")
        print("   This may be due to propagation delay. Try running the test again in a few moments.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
