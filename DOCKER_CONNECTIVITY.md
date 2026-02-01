# IDS2 SOC Pipeline - Architecture & Connectivity

## Overview

The IDS2 SOC Pipeline uses a Docker-based multi-container architecture optimized for Raspberry Pi 5. This document explains how containers communicate and how to verify connectivity.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        RASPBERRY PI 5 (8GB RAM, 4 cores)                  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                       Docker Network: ids2-network                  │  │
│  │                         (Bridge: 172.28.0.0/16)                     │  │
│  │                                                                      │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │  │
│  │  │   Vector     │───▶│    Redis     │    │  Prometheus  │         │  │
│  │  │  (1 core)    │    │  (0.5 core)  │    │  (0.5 core)  │         │  │
│  │  │   1024MB     │    │    512MB     │    │    512MB     │         │  │
│  │  │              │    │              │    │              │         │  │
│  │  │ Ports:       │    │ Port:        │    │ Port:        │         │  │
│  │  │  9101 (prom) │    │  6379        │    │  9090        │         │  │
│  │  │  8686 (api)  │    │              │    │              │         │  │
│  │  │  8282 (http) │    │              │    │              │         │  │
│  │  └──────┬───────┘    └──────────────┘    └──────┬───────┘         │  │
│  │         │                                         │                 │  │
│  │         │                                         │                 │  │
│  │         │            ┌──────────────┐             │                 │  │
│  │         └───────────▶│   Grafana    │◀────────────┘                 │  │
│  │                      │  (0.5 core)  │                               │  │
│  │                      │    512MB     │                               │  │
│  │                      │              │                               │  │
│  │                      │ Port: 3000   │                               │  │
│  │                      └──────────────┘                               │  │
│  │                                                                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      IDS2 Agent (Multi-Process)                     │  │
│  │                                                                      │  │
│  │  Process #1: Supervisor                                             │  │
│  │  Process #2: Resource Controller (monitors CPU/RAM)                 │  │
│  │  Process #3: Connectivity Checker (DNS/TLS/OpenSearch)              │  │
│  │  Process #4: Metrics Server (:9100)                                 │  │
│  │  Process #5: API Server (:5000)                                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      RAM Disk: /mnt/ram_logs                        │  │
│  │                         (512MB tmpfs)                               │  │
│  │                                                                      │  │
│  │                      eve.json (Suricata logs)                       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                    ▼                                       │
│                         AWS OpenSearch (us-east-1)                        │
│                            (SigV4 Authentication)                         │
└──────────────────────────────────────────────────────────────────────────┘
```

## Container Communication Flows

### 1. Vector → Redis (Fallback Buffer)
- **Purpose**: Store events when OpenSearch is unavailable
- **Protocol**: Redis protocol (RESP)
- **Port**: 6379
- **DNS**: `redis:6379`
- **Configuration**: `redis_url: redis://redis:6379/0` in vector.toml

### 2. Vector → AWS OpenSearch (Primary Sink)
- **Purpose**: Send events to OpenSearch for indexing
- **Protocol**: HTTPS (SigV4 signed requests)
- **Endpoint**: Retrieved from AWS API via boto3
- **Batch**: 100 events or 30s timeout
- **Compression**: gzip

### 3. Prometheus → Vector (Metrics Scraping)
- **Purpose**: Collect Vector performance metrics
- **Protocol**: HTTP (Prometheus format)
- **Port**: 9101
- **DNS**: `vector:9101`
- **Scrape Interval**: 15s (configured in prometheus.yml)

### 4. Prometheus → Agent (Metrics Scraping)
- **Purpose**: Collect agent metrics (CPU, RAM, throttle level)
- **Protocol**: HTTP (Prometheus format)
- **Port**: 9100 (exposed on host)
- **Target**: Host network (not container network)

### 5. Grafana → Prometheus (Data Source)
- **Purpose**: Query metrics for visualization
- **Protocol**: HTTP (Prometheus API)
- **Port**: 9090
- **DNS**: `prometheus:9090`
- **Configuration**: Auto-provisioned via datasources/prometheus.yml

### 6. External Access (from Raspberry Pi host or network)
- **Vector Metrics**: `http://<PI_IP>:9101/metrics`
- **Vector Health**: `http://<PI_IP>:8686/health`
- **Prometheus UI**: `http://<PI_IP>:9090`
- **Grafana Dashboard**: `http://<PI_IP>:3000` (admin/admin)
- **Agent Metrics**: `http://<PI_IP>:9100/metrics`
- **API Server**: `http://<PI_IP>:5000`
- **Redis**: `<PI_IP>:6379`

## Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            COMPLETE DATA FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

1. NETWORK CAPTURE
   eth0 (Raspberry Pi) → Suricata (af-packet, 2 threads)
   
2. LOG GENERATION
   Suricata → /mnt/ram_logs/eve.json (NDJSON format, one event per line)
   
3. LOG INGESTION
   Vector source (file) → Reads eve.json → Parses JSON
   
4. TRANSFORMATION
   Vector transform → Suricata JSON → Elastic Common Schema (ECS)
   Required fields:
   - @timestamp
   - ecs.version
   - event.* (type, category, action, outcome)
   - source.* (ip, port, geo)
   - destination.* (ip, port, geo)
   - network.* (protocol, direction, bytes)
   
5. BUFFERING
   Primary: Disk buffer (256MB at /var/lib/vector/buffer)
   Fallback: Redis (when OpenSearch slow/unavailable)
   
6. BATCHING
   Vector batch: 100 events or 30s timeout, whichever comes first
   Compression: gzip
   
7. DELIVERY
   Vector sink → AWS OpenSearch bulk API
   Endpoint: POST /_bulk
   Format: {"index":{"_index":"ids2-logs-2026.02.01"}}\n{...event...}\n
   Auth: AWS SigV4 (profile: moi33, region: us-east-1)
   Retry: 3 attempts with exponential backoff (2s → 10s)
   
8. INDEXING
   OpenSearch → Index: ids2-logs-YYYY.MM.DD
   Mapping: Automatic ECS field detection
   
9. VISUALIZATION
   Grafana → Query OpenSearch via Prometheus
   Dashboards: Pre-provisioned IDS2 dashboard
```

## Network Configuration

### Docker Network Details
- **Name**: `ids2-network`
- **Driver**: bridge
- **Subnet**: 172.28.0.0/16
- **Gateway**: 172.28.0.1

### Container IPs (dynamically assigned)
Containers receive IPs from the subnet. Use DNS names instead of IPs:
- `redis` → resolves to Redis container IP
- `vector` → resolves to Vector container IP
- `prometheus` → resolves to Prometheus container IP
- `grafana` → resolves to Grafana container IP

### Port Mapping (Host → Container)
| Service | Host Port | Container Port | Purpose |
|---------|-----------|----------------|---------|
| Vector | 9101 | 9101 | Prometheus metrics |
| Vector | 8686 | 8686 | Health check API |
| Vector | 8282 | 8282 | HTTP ingest (testing) |
| Redis | 6379 | 6379 | Redis protocol |
| Prometheus | 9090 | 9090 | Prometheus UI & API |
| Grafana | 3000 | 3000 | Grafana web UI |
| Agent | 9100 | 9100 | Agent metrics |
| API Server | 5000 | 5000 | Flask REST API |

## Connectivity Testing

### Automated Test Script
Run the comprehensive connectivity test:

```bash
./deploy/test_docker_connectivity.sh
```

This script performs 10 tests:
1. ✅ Docker Compose stack verification
2. ✅ Docker network creation check
3. ✅ DNS resolution between containers
4. ✅ Port connectivity between services
5. ✅ Health check verification
6. ✅ HTTP endpoint accessibility
7. ✅ Prometheus metrics scraping
8. ✅ Redis fallback connectivity
9. ✅ External port accessibility from host
10. ✅ End-to-end data flow test

### Manual Connectivity Tests

#### Test 1: Check all containers are running
```bash
docker-compose -f docker/docker-compose.yml ps
```

Expected output: All containers should show "Up" status.

#### Test 2: Check network
```bash
docker network inspect ids2-network
```

Expected: All containers listed in "Containers" section.

#### Test 3: Test DNS from Vector to Redis
```bash
docker exec ids2-vector getent hosts redis
```

Expected: Returns Redis container IP.

#### Test 4: Test Redis connectivity
```bash
docker exec ids2-redis redis-cli ping
```

Expected: Returns "PONG".

#### Test 5: Test Vector health endpoint
```bash
curl http://localhost:8686/health
```

Expected: Returns health status JSON.

#### Test 6: Test Prometheus scraping Vector
```bash
docker exec ids2-prometheus wget -q -O- http://vector:9101/metrics | head
```

Expected: Returns Prometheus metrics from Vector.

#### Test 7: Test Grafana → Prometheus connection
```bash
# Login to Grafana UI at http://<PI_IP>:3000
# Username: admin, Password: admin (from .env)
# Check Configuration → Data Sources → Prometheus
```

Expected: Prometheus data source shows "Data source is working".

## Troubleshooting Connectivity Issues

### Issue: Container cannot resolve DNS names

**Diagnosis:**
```bash
docker exec <container_name> getent hosts <target_name>
```

**Solution:**
1. Verify both containers are on the same network:
   ```bash
   docker network inspect ids2-network
   ```
2. Restart the container:
   ```bash
   docker-compose -f docker/docker-compose.yml restart <service_name>
   ```

### Issue: Port not accessible between containers

**Diagnosis:**
```bash
docker exec <source_container> timeout 5 bash -c "cat < /dev/null > /dev/tcp/<target>/port"
```

**Solution:**
1. Check if target container is listening:
   ```bash
   docker exec <target_container> netstat -tlnp
   ```
2. Check firewall rules (should not affect container-to-container):
   ```bash
   sudo iptables -L
   ```

### Issue: External port not accessible from host

**Diagnosis:**
```bash
curl -v http://localhost:<port>
```

**Solution:**
1. Verify port mapping in docker-compose.yml
2. Check if container is healthy:
   ```bash
   docker inspect <container_name> | grep Health
   ```
3. Check container logs:
   ```bash
   docker logs <container_name>
   ```

### Issue: Metrics not appearing in Prometheus

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq
```

**Solution:**
1. Verify prometheus.yml configuration
2. Check Vector metrics endpoint:
   ```bash
   curl http://localhost:9101/metrics
   ```
3. Restart Prometheus:
   ```bash
   docker-compose -f docker/docker-compose.yml restart prometheus
   ```

## Resource Constraints

All containers have resource limits to prevent Pi overload:

| Service | CPU Limit | RAM Limit | CPU Reserve | RAM Reserve |
|---------|-----------|-----------|-------------|-------------|
| Vector | 1.0 | 1024M | 0.5 | 512M |
| Redis | 0.5 | 512M | 0.25 | 256M |
| Prometheus | 0.5 | 512M | 0.25 | 256M |
| Grafana | 0.5 | 512M | 0.25 | 256M |
| **Total** | **2.5** | **2560M** | **1.25** | **1280M** |

This leaves:
- **1.5 CPU cores** for Suricata (2 threads on cores 2-3) + Agent
- **~5GB RAM** for Suricata + Agent + System

## Security Considerations

1. **Network Isolation**: All containers on private bridge network
2. **Read-only Configs**: Configuration files mounted read-only (`:ro`)
3. **AWS Credentials**: Mounted read-only from `~/.aws`
4. **Non-root User**: Agent container runs as user `ids2` (UID 1000)
5. **No Privileged Mode**: No containers run with `--privileged`

## Deployment Checklist

Before deploying to Raspberry Pi:

- [ ] Ensure Docker and Docker Compose are installed
- [ ] Create RAM disk: `sudo ./deploy/setup_ramdisk.sh`
- [ ] Configure AWS credentials: `aws configure --profile moi33`
- [ ] Set environment variables in `.env` file
- [ ] Verify network: `./deploy/network_eth0_only.sh` (optional, eth0 only)
- [ ] Build and start stack: `docker-compose -f docker/docker-compose.yml up -d`
- [ ] Test connectivity: `./deploy/test_docker_connectivity.sh`
- [ ] Verify health: `docker-compose -f docker/docker-compose.yml ps`
- [ ] Access Grafana: `http://<PI_IP>:3000`

## References

- Docker Compose file: `docker/docker-compose.yml`
- Prometheus config: `docker/prometheus.yml`
- Grafana provisioning: `docker/grafana/provisioning/`
- Vector config template: `vector/vector.toml.template`
- Connectivity test: `deploy/test_docker_connectivity.sh`
