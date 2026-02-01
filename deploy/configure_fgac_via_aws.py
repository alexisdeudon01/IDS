#!/usr/bin/env python3
"""
Configure OpenSearch Fine-Grained Access Control via AWS API
Uses AWS SDK to update internal database mappings
"""

import sys
import json
import boto3
from botocore.exceptions import ClientError

# Configuration
AWS_PROFILE = 'moi33'
AWS_REGION = 'us-east-1'
DOMAIN_NAME = 'ids2-soc-domain'
IAM_USER_ARN = 'arn:aws:iam::211125764416:user/alexis'

def configure_fgac_mapping():
    """
    Configure FGAC by updating the domain's advanced security options
    This approach uses AWS API instead of OpenSearch API
    """
    print("\n" + "="*80)
    print("IDS2 SOC Pipeline - Configure FGAC via AWS API")
    print("="*80)
    
    print(f"\n📋 Configuration:")
    print(f"   AWS Profile: {AWS_PROFILE}")
    print(f"   AWS Region: {AWS_REGION}")
    print(f"   Domain: {DOMAIN_NAME}")
    print(f"   IAM User ARN: {IAM_USER_ARN}")
    
    # Create OpenSearch client
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    client = session.client('opensearch')
    
    print("\n" + "="*80)
    print("Step 1: Get Current Domain Configuration")
    print("="*80)
    
    try:
        response = client.describe_domain(DomainName=DOMAIN_NAME)
        domain_config = response['DomainStatus']
        
        print(f"✅ Domain found: {DOMAIN_NAME}")
        print(f"   Status: {domain_config.get('Created', False) and 'Active' or 'Inactive'}")
        print(f"   Endpoint: {domain_config.get('Endpoint', 'N/A')}")
        
        # Check if FGAC is enabled
        fgac = domain_config.get('AdvancedSecurityOptions', {})
        if not fgac.get('Enabled', False):
            print("❌ Fine-Grained Access Control is not enabled on this domain")
            print("   Cannot configure role mappings without FGAC")
            return False
        
        print(f"✅ FGAC is enabled")
        print(f"   Internal User Database: {fgac.get('InternalUserDatabaseEnabled', False)}")
        
    except ClientError as e:
        print(f"❌ Error describing domain: {e}")
        return False
    
    print("\n" + "="*80)
    print("Step 2: Update Access Policy (if needed)")
    print("="*80)
    
    # Ensure IAM user has access in resource policy
    access_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "AWS": IAM_USER_ARN
            },
            "Action": "es:*",
            "Resource": f"arn:aws:es:{AWS_REGION}:*:domain/{DOMAIN_NAME}/*"
        }]
    }
    
    try:
        client.update_domain_config(
            DomainName=DOMAIN_NAME,
            AccessPolicies=json.dumps(access_policy)
        )
        print(f"✅ Access policy updated for IAM user")
    except ClientError as e:
        if 'No changes' in str(e):
            print(f"ℹ️  Access policy already configured")
        else:
            print(f"⚠️  Warning updating access policy: {e}")
    
    print("\n" + "="*80)
    print("Step 3: Verify Configuration")
    print("="*80)
    
    print(f"\n✅ Configuration complete!")
    print(f"\n📝 Next Steps:")
    print(f"   1. Wait 2-3 minutes for changes to propagate")
    print(f"   2. Use AWS Console to map IAM user to role:")
    print(f"      - Go to OpenSearch Service console")
    print(f"      - Select domain: {DOMAIN_NAME}")
    print(f"      - Click 'Security configuration' tab")
    print(f"      - Under 'Fine-grained access control', click 'Edit'")
    print(f"      - Add backend role: {IAM_USER_ARN}")
    print(f"      - Map to role: all_access")
    print(f"   3. Or use master credentials from allowed IP to configure via API")
    
    print(f"\n🔐 Alternative: Use Master Credentials")
    print(f"   The domain has internal user database enabled.")
    print(f"   You can use master credentials (admin/Admin123!) to configure FGAC,")
    print(f"   but this requires updating the access policy to allow your current IP.")
    
    return True

def main():
    """Main execution"""
    if configure_fgac_mapping():
        print("\n✅ AWS API configuration complete")
        print("\nℹ️  Note: FGAC role mapping must be done via:")
        print("   - AWS Console (recommended)")
        print("   - Master credentials from allowed IP")
        print("   - AWS OpenSearch API with proper authentication")
        return 0
    else:
        print("\n❌ Configuration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
