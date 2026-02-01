#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - Vector → OpenSearch End-to-End Test

This script:
1. Starts Redis and Vector containers
2. Sends sample events via HTTP to Vector
3. Verifies documents appear in OpenSearch
4. Tears down the stack
"""

import sys
import json
import time
import subprocess
import requests
from typing import Dict, Any, List
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python_env" / "modules"))

from config_manager import ConfigManager

# Load configuration
try:
    config_manager = ConfigManager()
    aws_config = config_manager.get_aws_config()
    opensearch_credentials = config_manager.get_opensearch_credentials()
    docker_config = config_manager.get_docker_config()
    vector_config = config_manager.get_vector_config()
    
    AWS_PROFILE = aws_config['profile']
    AWS_REGION = aws_config['region']
    DOMAIN_NAME = aws_config['domain_name']
    ENDPOINT = aws_config['endpoint']
    BASE_URL = f'https://{ENDPOINT}'
    MASTER_USER = opensearch_credentials['master_user']
    MASTER_PASS = opensearch_credentials['master_pass']
    
    VECTOR_HTTP_PORT = vector_config.get('http_port', 8282)
    COMPOSE_FILE = docker_config.get('compose_file', 'docker/docker-compose.yml')

except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    sys.exit(1)

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
credentials = session.get_credentials()

def print_section(title: str):
    print(f"\n{'='*80}")
    print(title)
    print('='*80)

def run_command(cmd: List[str], timeout: int = 60) -> tuple:
    """Run shell command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', 'Command timed out'
    except Exception as e:
        return False, '', str(e)

def sigv4_request(method: str, path: str, body: str = None, headers: Dict[str, str] = None):
    """Make SigV4-signed request to OpenSearch"""
    url = f'{BASE_URL}{path}'
    hdrs = headers.copy() if headers else {}
    request = AWSRequest(method=method, url=url, data=body, headers=hdrs)
    SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
    return requests.request(method, url, headers=dict(request.headers), data=body, timeout=20)

def start_services() -> bool:
    """Start Redis and Vector containers"""
    print_section("Starting Docker Services (Redis + Vector)")
    
    # Stop any existing containers
    print("Stopping existing containers...")
    run_command(['docker', 'compose', '-f', COMPOSE_FILE, 'down'], timeout=30)
    time.sleep(2)
    
    # Start Redis
    print("Starting Redis...")
    success, stdout, stderr = run_command(
        ['docker', 'compose', '-f', COMPOSE_FILE, 'up', '-d', 'redis'],
        timeout=60
    )
    if not success:
        print(f"❌ Failed to start Redis: {stderr}")
        return False
    print("✅ Redis started")
    
    # Wait for Redis health
    print("Waiting for Redis health check...")
    for i in range(30):
        success, stdout, _ = run_command(['docker', 'exec', 'ids2-redis', 'redis-cli', 'ping'])
        if success and 'PONG' in stdout:
            print("✅ Redis is healthy")
            break
        time.sleep(1)
    else:
        print("❌ Redis health check timeout")
        return False
    
    # Start Vector
    print("Starting Vector...")
    success, stdout, stderr = run_command(
        ['docker', 'compose', '-f', COMPOSE_FILE, 'up', '-d', 'vector'],
        timeout=120
    )
    if not success:
        print(f"❌ Failed to start Vector: {stderr}")
        return False
    print("✅ Vector started")
    
    # Wait for Vector health
    print("Waiting for Vector health check (up to 60s)...")
    for i in range(60):
        try:
            r = requests.get('http://localhost:8686/health', timeout=2)
            if r.status_code == 200:
                print(f"✅ Vector is healthy (took {i+1}s)")
                return True
        except:
            pass
        time.sleep(1)
    
    print("❌ Vector health check timeout")
    # Show logs for debugging
    run_command(['docker', 'logs', '--tail', '50', 'ids2-vector'])
    return False

def send_sample_events() -> bool:
    """Send sample events to Vector via HTTP"""
    print_section("Sending Sample Events to Vector")
    
    events = [
        {
            "timestamp": "2024-02-01T12:00:00.000Z",
            "event_type": "alert",
            "src_ip": "192.168.1.100",
            "src_port": 54321,
            "dest_ip": "10.0.0.50",
            "dest_port": 443,
            "proto": "TCP",
            "alert": {
                "signature": "ET MALWARE Suspicious TLS Certificate",
                "signature_id": 2024001,
                "severity": 1,
                "category": "Malware"
            }
        },
        {
            "timestamp": "2024-02-01T12:01:00.000Z",
            "event_type": "http",
            "src_ip": "192.168.1.101",
            "src_port": 55432,
            "dest_ip": "93.184.216.34",
            "dest_port": 80,
            "proto": "TCP",
            "http": {
                "http_method": "GET",
                "url": "/api/data",
                "hostname": "example.com",
                "status": 200,
                "protocol": "HTTP/1.1"
            }
        },
        {
            "timestamp": "2024-02-01T12:02:00.000Z",
            "event_type": "dns",
            "src_ip": "192.168.1.102",
            "src_port": 53210,
            "dest_ip": "8.8.8.8",
            "dest_port": 53,
            "proto": "UDP",
            "dns": {
                "rrname": "malicious-domain.com",
                "rrtype": "A",
                "rcode": "NOERROR"
            }
        }
    ]
    
    url = f'http://localhost:{VECTOR_HTTP_PORT}/'
    sent_count = 0
    
    for i, event in enumerate(events, 1):
        try:
            r = requests.post(url, json=event, timeout=5)
            if r.status_code in (200, 201, 204):
                print(f"✅ Event {i}/3 sent successfully")
                sent_count += 1
            else:
                print(f"❌ Event {i}/3 failed: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"❌ Event {i}/3 error: {e}")
    
    if sent_count == len(events):
        print(f"\n✅ All {sent_count} events sent successfully")
        return True
    else:
        print(f"\n⚠️  Only {sent_count}/{len(events)} events sent")
        return sent_count > 0

def verify_opensearch_ingestion() -> bool:
    """Verify documents appeared in OpenSearch"""
    print_section("Verifying OpenSearch Ingestion")
    
    # Wait for Vector to process and send to OpenSearch
    print("Waiting 30s for Vector to process and send events...")
    time.sleep(30)
    
    # Check indices
    print("\nChecking indices...")
    r = sigv4_request('GET', '/_cat/indices/ids2-logs-*?format=json')
    if r.status_code != 200:
        print(f"❌ Failed to list indices: {r.status_code}")
        print(r.text[:200])
        return False
    
    indices = r.json()
    if not indices:
        print("❌ No ids2-logs-* indices found")
        return False
    
    print(f"✅ Found {len(indices)} index(es):")
    for idx in indices:
        print(f"   - {idx['index']}: {idx.get('docs.count', 0)} docs")
    
    # Count documents across all ids2-logs-* indices
    print("\nCounting documents...")
    r = sigv4_request('GET', '/ids2-logs-*/_count')
    if r.status_code != 200:
        print(f"❌ Failed to count documents: {r.status_code}")
        print(r.text[:200])
        return False
    
    count = r.json().get('count', 0)
    print(f"Total documents in ids2-logs-*: {count}")
    
    if count >= 3:
        print(f"✅ Found {count} documents (expected at least 3)")
        
        # Sample a document
        print("\nSampling a document...")
        query = json.dumps({"query": {"match_all": {}}, "size": 1})
        r = sigv4_request('POST', '/ids2-logs-*/_search', body=query, headers={'Content-Type': 'application/json'})
        if r.status_code == 200:
            hits = r.json().get('hits', {}).get('hits', [])
            if hits:
                doc = hits[0]['_source']
                print(f"Sample document:")
                print(f"  - @timestamp: {doc.get('@timestamp', 'N/A')}")
                print(f"  - event.kind: {doc.get('event', {}).get('kind', 'N/A')}")
                print(f"  - source.ip: {doc.get('source', {}).get('ip', 'N/A')}")
                print(f"  - destination.ip: {doc.get('destination', {}).get('ip', 'N/A')}")
        
        return True
    elif count > 0:
        print(f"⚠️  Found {count} documents (expected 3)")
        return True
    else:
        print("❌ No documents found in OpenSearch")
        return False

def cleanup_test_data() -> bool:
    """Clean up test indices"""
    print_section("Cleaning Up Test Data")
    
    print("Deleting ids2-logs-* indices...")
    r = sigv4_request('DELETE', '/ids2-logs-*')
    if r.status_code in (200, 404):
        print("✅ Test indices deleted")
        return True
    else:
        print(f"⚠️  Failed to delete indices: {r.status_code}")
        return False

def stop_services() -> bool:
    """Stop Docker services"""
    print_section("Stopping Docker Services")
    
    success, stdout, stderr = run_command(
        ['docker', 'compose', '-f', COMPOSE_FILE, 'down'],
        timeout=60
    )
    if success:
        print("✅ Services stopped")
        return True
    else:
        print(f"⚠️  Failed to stop services: {stderr}")
        return False

def main():
    """Main execution"""
    print_section("Vector → OpenSearch End-to-End Test")
    
    results = []
    
    # Step 1: Start services
    if not start_services():
        print("\n❌ Failed to start services")
        stop_services()
        return 1
    results.append(("Start services", True))
    
    # Step 2: Send events
    events_sent = send_sample_events()
    results.append(("Send events", events_sent))
    
    if not events_sent:
        print("\n❌ Failed to send events")
        stop_services()
        return 1
    
    # Step 3: Verify ingestion
    ingestion_ok = verify_opensearch_ingestion()
    results.append(("Verify ingestion", ingestion_ok))
    
    # Step 4: Cleanup
    cleanup_ok = cleanup_test_data()
    results.append(("Cleanup test data", cleanup_ok))
    
    # Step 5: Stop services
    stop_ok = stop_services()
    results.append(("Stop services", stop_ok))
    
    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        print(f"- {name}: {'✅ PASS' if ok else '❌ FAIL'}")
    
    print(f"\nTotal: {passed}/{total} steps passed")
    
    if passed == total:
        print("\n✅ Vector → OpenSearch E2E test PASSED!")
        return 0
    else:
        print("\n❌ Vector → OpenSearch E2E test FAILED")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        stop_services()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        stop_services()
        sys.exit(1)
