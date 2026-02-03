#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - Docker Network Topology Visualizer
Generates a visual representation of container connectivity
"""

import subprocess
import json
import sys

def get_network_info():
    """Get Docker network information"""
    try:
        result = subprocess.run(
            ['docker', 'network', 'inspect', 'ids2-network'],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)[0]
    except subprocess.CalledProcessError:
        print("❌ Error: ids2-network not found. Is the stack running?")
        print("   Run: docker-compose -f docker/docker-compose.yml up -d")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: Docker not found. Is Docker installed?")
        sys.exit(1)

def get_container_info():
    """Get information about all containers"""
    try:
        result = subprocess.run(
            ['docker-compose', '-f', 'docker/docker-compose.yml', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                containers.append(json.loads(line))
        return containers
    except subprocess.CalledProcessError:
        print("⚠️  Warning: Could not get container status")
        return []

def visualize_topology(network_info, containers):
    """Display network topology"""
    print("\n" + "="*80)
    print("IDS2 SOC PIPELINE - DOCKER NETWORK TOPOLOGY")
    print("="*80 + "\n")
    
    # Network details
    print(f"📡 Network: {network_info['Name']}")
    print(f"   Driver: {network_info['Driver']}")
    print(f"   Subnet: {network_info['IPAM']['Config'][0]['Subnet']}")
    print(f"   Gateway: {network_info['IPAM']['Config'][0]['Gateway']}")
    print()
    
    # Container topology
    print("🐳 Container Topology:")
    print()
    
    container_map = {c['Service']: c for c in containers}
    
    # Visual representation
    print("    ┌─────────────────────────────────────────────────────────┐")
    print("    │              ids2-network (172.28.0.0/16)               │")
    print("    └─────────────────────────────────────────────────────────┘")
    print()
    
    # Vector container
    if 'vector' in container_map:
        c = container_map['vector']
        status = "🟢" if c['State'] == 'running' else "🔴"
        print(f"    ┌─────────────────────────────────────────────┐")
        print(f"    │  {status} Vector (ids2-vector)                   │")
        print(f"    │     Status: {c['State']:20}           │")
        print(f"    │     Ports: 9101, 8686, 8282                │")
        print(f"    └─────────────────────────────────────────────┘")
        print("              │                    │")
        print("              │                    │")
        print("              ▼                    ▼")
    
    # Redis and Prometheus (parallel)
    print("    ┌─────────────────┐      ┌─────────────────┐")
    
    if 'redis' in container_map:
        c = container_map['redis']
        status = "🟢" if c['State'] == 'running' else "🔴"
        print(f"    │ {status} Redis        │      │ {status} Prometheus   │")
        print(f"    │   ids2-redis    │      │   ids2-prom.  │")
        print(f"    │   Port: 6379    │      │   Port: 9090  │")
    else:
        print(f"    │ 🔴 Redis        │      │ 🔴 Prometheus   │")
    
    print("    └─────────────────┘      └─────────────────┘")
    print("                                     │")
    print("                                     │")
    print("                                     ▼")
    
    # Grafana
    if 'grafana' in container_map:
        c = container_map['grafana']
        status = "🟢" if c['State'] == 'running' else "🔴"
        print(f"              ┌─────────────────────────────┐")
        print(f"              │ {status} Grafana (ids2-grafana)  │")
        print(f"              │   Status: {c['State']:14}  │")
        print(f"              │   Port: 3000                │")
        print(f"              └─────────────────────────────┘")
    
    print()
    
    # Connection details
    print("🔗 Container Connections:")
    print()
    print("   Vector → Redis")
    print("     • Purpose: Fallback buffer when OpenSearch unavailable")
    print("     • Protocol: Redis (RESP)")
    print("     • DNS: redis:6379")
    print()
    print("   Vector → OpenSearch")
    print("     • Purpose: Primary log sink")
    print("     • Protocol: HTTPS (AWS SigV4)")
    print("     • Batch: 100 events / 30s")
    print()
    print("   Prometheus → Vector")
    print("     • Purpose: Scrape metrics")
    print("     • Protocol: HTTP")
    print("     • DNS: vector:9101")
    print("     • Interval: 15s")
    print()
    print("   Grafana → Prometheus")
    print("     • Purpose: Query metrics")
    print("     • Protocol: HTTP")
    print("     • DNS: prometheus:9090")
    print()
    
    # External access
    print("🌐 External Access (from host):")
    print()
    for service in ['vector', 'redis', 'prometheus', 'grafana']:
        if service in container_map:
            c = container_map[service]
            if c.get('Publishers'):
                for pub in c['Publishers']:
                    port = pub.get('PublishedPort', 'N/A')
                    target = pub.get('TargetPort', 'N/A')
                    print(f"   • {service:12} → localhost:{port:5} → container:{target}")
    
    print()
    
    # Health status summary
    print("💊 Health Status:")
    print()
    total = len(containers)
    running = sum(1 for c in containers if c['State'] == 'running')
    print(f"   Running: {running}/{total}")
    
    if running < total:
        print()
        print("   ⚠️  Some containers are not running!")
        for c in containers:
            if c['State'] != 'running':
                print(f"      • {c['Service']}: {c['State']}")
    
    print()
    print("="*80)
    print()

def main():
    """Main function"""
    print("\n🔍 Inspecting Docker network topology...")
    
    network_info = get_network_info()
    containers = get_container_info()
    
    visualize_topology(network_info, containers)
    
    print("💡 Tips:")
    print("   • Test connectivity: ./deploy/test_docker_connectivity.sh")
    print("   • View logs: docker-compose -f docker/docker-compose.yml logs -f")
    print("   • Restart: docker-compose -f docker/docker-compose.yml restart")
    print()

if __name__ == '__main__':
    main()
