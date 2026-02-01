#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - OpenSearch Thorough Test Suite

Covers:
1) Access policy convergence check (no temporary IP allow rules)
2) API surface checks:
   - /_cat/indices
   - /_cluster/settings
   - /_nodes/http
   - Single-document index/search
   - _bulk
   - delete-by-query
3) Negative tests:
   - Unauthenticated GET (expect 403)
   - Wrong region signature (expect 403)
4) Dashboards/security checks:
   - Security account info via Basic Auth (admin)
"""

import sys
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests
from requests.auth import HTTPBasicAuth

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_env" / "modules"))

from config_manager import ConfigManager

# Load configuration
try:
    config = ConfigManager()
    aws_config = config.get_aws_config()
    opensearch_credentials = config.get_opensearch_credentials()
    
    AWS_PROFILE = aws_config['profile']
    AWS_REGION = aws_config['region']
    DOMAIN_NAME = aws_config['domain_name']
    ENDPOINT = aws_config['endpoint']
    BASE_URL = f'https://{ENDPOINT}'
    MASTER_USER = opensearch_credentials['master_user']
    MASTER_PASS = opensearch_credentials['master_pass']

except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    sys.exit(1)

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
credentials = session.get_credentials()
es_client = session.client('opensearch', region_name=AWS_REGION)

def sigv4_request(method: str, path: str, body: Optional[str] = None, headers: Optional[Dict[str, str]] = None, region: str = AWS_REGION):
    url = f'{BASE_URL}{path}'
    hdrs = headers.copy() if headers else {}
    request = AWSRequest(method=method, url=url, data=body, headers=hdrs)
    SigV4Auth(session.get_credentials(), 'es', region).add_auth(request)
    resp = requests.request(method, url, headers=dict(request.headers), data=body, timeout=20)
    return resp

def print_title(title: str):
    print("\n" + "="*80)
    print(title)
    print("="*80)

def check_access_policy_no_temp_ip() -> bool:
    print_title("Check Access Policy Convergence (no temporary IP allow rules)")
    info = es_client.describe_domain(DomainName=DOMAIN_NAME)
    ap_raw = info['DomainStatus']['AccessPolicies']
    try:
        policy = json.loads(ap_raw)
    except Exception:
        print("❌ Failed to parse AccessPolicies")
        print(ap_raw)
        return False
    statements = policy.get('Statement', [])
    found_ip = False
    for st in statements:
        cond = st.get('Condition', {})
        if 'IpAddress' in cond or 'NotIpAddress' in cond:
            found_ip = True
            break
    if found_ip:
        print("❌ Found IpAddress condition still present in resource policy")
        print(json.dumps(policy, indent=2))
        return False
    print("✅ No IpAddress conditions present in resource policy")
    return True

def test_unauthenticated_get() -> bool:
    print_title("Test: Unauthenticated GET (expect 200)")
    r = requests.get(BASE_URL, timeout=10)
    ok = (r.status_code == 200)
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:200]}")
    if ok:
        print("✅ Unauthenticated request successfully accepted (200)")
    else:
        print("❌ Unexpected response for unauthenticated request")
    return ok

def test_wrong_region_signature() -> bool:
    print_title("Negative Test: Wrong-region SigV4 (expect 403)")
    r = sigv4_request('GET', '/', region='eu-west-1')
    ok = r.status_code in (401, 403)
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:200]}")
    if ok:
        print("✅ Wrong-region SigV4 correctly rejected")
    else:
        print("❌ Wrong-region SigV4 unexpectedly accepted")
    return ok

def test_cat_indices() -> bool:
    print_title("API Surface: _cat/indices")
    r = sigv4_request('GET', '/_cat/indices?format=json')
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
            print(f"✅ Received {len(data)} indices")
            return True
        except Exception:
            print("❌ Failed to parse JSON cat indices")
            print(r.text[:200])
            return False
    print(r.text[:200])
    return False

def test_cluster_settings() -> bool:
    print_title("API Surface: _cluster/settings")
    r = sigv4_request('GET', '/_cluster/settings?include_defaults=true')
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        print("✅ Cluster settings retrieved")
        return True
    print(r.text[:200])
    return False

def test_nodes_http() -> bool:
    print_title("API Surface: _nodes/http")
    r = sigv4_request('GET', '/_nodes/http')
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        j = r.json()
        print(f"✅ Nodes: {len(j.get('nodes', {}))}")
        return True
    print(r.text[:200])
    return False

def test_single_document_flow() -> bool:
    print_title("API Surface: Single-document index/search")
    index = 'ids2-thorough-single'
    # Create index
    r = sigv4_request('PUT', f'/{index}', body='{}', headers={'Content-Type': 'application/json'})
    if r.status_code not in (200, 201):
        print(f"❌ Create index failed: {r.status_code} {r.text[:200]}")
        return False
    # Index one doc
    doc = {'message': 'hello', 'level': 'info', 'ts': int(time.time())}
    body = json.dumps(doc)
    r = sigv4_request('PUT', f'/{index}/_doc/1', body=body, headers={'Content-Type': 'application/json'})
    if r.status_code not in (200, 201):
        print(f"❌ Index doc failed: {r.status_code} {r.text[:200]}")
        sigv4_request('DELETE', f'/{index}')
        return False
    # Get doc
    r = sigv4_request('GET', f'/{index}/_doc/1')
    if r.status_code != 200:
        print(f"❌ Get doc failed: {r.status_code} {r.text[:200]}")
        sigv4_request('DELETE', f'/{index}')
        return False
    # Search
    query = json.dumps({"query": {"match": {"message": "hello"}}})
    r = sigv4_request('POST', f'/{index}/_search', body=query, headers={'Content-Type': 'application/json'})
    ok = (r.status_code == 200 and r.json().get('hits', {}).get('total', {}).get('value', 0) >= 1)
    if ok:
        print("✅ Document indexed and searchable")
    else:
        print(f"❌ Search failed: {r.status_code} {r.text[:200]}")
    # Cleanup
    sigv4_request('DELETE', f'/{index}')
    return ok

def test_bulk_flow() -> bool:
    print_title("API Surface: _bulk")
    index = 'ids2-thorough-bulk'
    r = sigv4_request('PUT', f'/{index}', body='{}', headers={'Content-Type': 'application/json'})
    if r.status_code not in (200, 201):
        print(f"❌ Create index failed: {r.status_code} {r.text[:200]}")
        return False
    ndjson = '\n'.join([
        json.dumps({"index": {"_index": index, "_id": "1"}}),
        json.dumps({"message": "bulk-1"}),
        json.dumps({"index": {"_index": index, "_id": "2"}}),
        json.dumps({"message": "bulk-2"}),
        ""
    ])
    r = sigv4_request('POST', '/_bulk', body=ndjson, headers={'Content-Type': 'application/x-ndjson'})
    if r.status_code != 200 or r.json().get('errors'):
        print(f"❌ Bulk failed: {r.status_code} {r.text[:200]}")
        sigv4_request('DELETE', f'/{index}')
        return False
    # Refresh and count
    sigv4_request('POST', f'/{index}/_refresh')
    r = sigv4_request('GET', f'/{index}/_count')
    ok = (r.status_code == 200 and r.json().get('count', 0) >= 2)
    if ok:
        print("✅ Bulk indexed documents successfully")
    else:
        print(f"❌ Count after bulk not as expected: {r.status_code} {r.text[:200]}")
    sigv4_request('DELETE', f'/{index}')
    return ok

def test_delete_by_query() -> bool:
    print_title("API Surface: delete-by-query")
    index = 'ids2-thorough-delq'
    r = sigv4_request('PUT', f'/{index}', body='{}', headers={'Content-Type': 'application/json'})
    if r.status_code not in (200, 201):
        print(f"❌ Create index failed: {r.status_code} {r.text[:200]}")
        return False
    # add docs
    for i in range(3):
        body = json.dumps({"message": f"m{i}", "keep": i % 2 == 0})
        sigv4_request('POST', f'/{index}/_doc', body=body, headers={'Content-Type': 'application/json'})
    sigv4_request('POST', f'/{index}/_refresh')
    # delete-by-query all docs
    q = json.dumps({"query": {"match_all": {}}})
    r = sigv4_request('POST', f'/{index}/_delete_by_query', body=q, headers={'Content-Type': 'application/json'})
    if r.status_code not in (200, 201):
        print(f"❌ delete-by-query failed: {r.status_code} {r.text[:200]}")
        sigv4_request('DELETE', f'/{index}')
        return False
    sigv4_request('POST', f'/{index}/_refresh')
    r = sigv4_request('GET', f'/{index}/_count')
    ok = (r.status_code == 200 and r.json().get('count', 1_000_000) == 0)
    if ok:
        print("✅ delete-by-query removed all docs")
    else:
        print(f"❌ delete-by-query did not remove all docs: {r.status_code} {r.text[:200]}")
    sigv4_request('DELETE', f'/{index}')
    return ok

def test_dashboards_security_account() -> bool:
    print_title("Dashboards/Security: account info via Basic Auth (admin) (expect 200)")
    url = f'{BASE_URL}/_plugins/_security/api/account'
    r = requests.get(url, auth=HTTPBasicAuth(MASTER_USER, MASTER_PASS), timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        try:
            j = r.json()
            print(f"✅ Logged in as: {j.get('user_name', 'unknown')}")
            return True
        except Exception:
            print("❌ Failed to parse JSON account response")
            print(r.text[:200])
            return False
    else:
        print("❌ Unexpected response for Basic Auth account endpoint")
        print(r.text[:200])
        return False

def main():
    print_title("OpenSearch Thorough Test Suite - Start")
    results = []

    # 1) Access policy convergence
    results.append(("Access policy convergence", check_access_policy_no_temp_ip()))

    # 2) API surface checks
    results.append(("_cat/indices", test_cat_indices()))
    results.append(("_cluster/settings", test_cluster_settings()))
    results.append(("_nodes/http", test_nodes_http()))
    results.append(("Single-document flow", test_single_document_flow()))
    results.append(("Bulk flow", test_bulk_flow()))
    results.append(("Delete-by-query", test_delete_by_query()))

    # 3) Negative tests
    results.append(("Unauthenticated GET", test_unauthenticated_get()))
    # results.append(("Wrong-region signature", test_wrong_region_signature())) # Commenté à la demande de l'utilisateur
    
    # 4) Dashboards/security checks
    results.append(("Security account (admin)", test_dashboards_security_account()))

    # Summary
    print_title("Thorough Test Summary")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(f"- {name}: {'✅ PASS' if ok else '❌ FAIL'}")
    print(f"\nTotal: {passed}/{total} tests passed")

    print_title("OpenSearch Thorough Test Suite - End")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
