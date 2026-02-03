# IDS2 SOC Pipeline - One-Command Deployment Guide

## Quick Start

Deploy the entire IDS2 SOC Pipeline to your Raspberry Pi 5 with one command:

```bash
./deploy/deploy_and_test.sh
```

This guide explains what happens under the hood and how to customize the deployment.

## Prerequisites

### On Your Development Machine
- Linux, macOS, or WSL2
- SSH access to Raspberry Pi
- Git
- Python 3.9+
- AWS CLI configured with profile `moi33`

### On Raspberry Pi 5
- Raspberry Pi OS (Debian Bookworm)
- 8GB RAM
- 64GB+ SD card
- Ethernet connection (eth0)
- Internet access

## Deployment Architecture

The deployment creates a **containerized multi-process SOC pipeline**:

```
┌─────────────────────────────────────────────────────────┐
│                    DEPLOYMENT LAYERS                     │
├─────────────────────────────────────────────────────────┤
│ Layer 1: Infrastructure (RAM disk, network, systemd)    │
│ Layer 2: Docker Stack (Vector, Redis, Prometheus, etc)  │
│ Layer 3: Python Agent (Multi-process orchestrator)      │
│ Layer 4: Monitoring (Metrics, health checks, logs)      │
└─────────────────────────────────────────────────────────┘
```

## Docker Container Overview

The deployment creates **ONE main Docker image** (`ids2-agent:latest`) that runs the Python multi-process agent. This agent then **orchestrates** several service containers:

### Main Orchestrator Container: `ids2-agent`
- **Image**: `ids2-agent:latest` (built from `Dockerfile`)
- **Purpose**: Runs the Python multi-process supervisor
- **Processes**:
  - Supervisor (agent_mp.py)
  - Resource Controller
  - Connectivity Checker
  - Metrics Server (:9100)
  - API Server (:5000)
- **CPU**: 1.5 cores
- **RAM**: 2048MB
- **Manages**: Docker socket to control other containers

### Service Containers (Orchestrated by Agent)

#### 1. Vector (`ids2-vector`)
- **Image**: `timberio/vector:0.34.0-debian`
- **Purpose**: Log ingestion, ECS transformation, OpenSearch delivery
- **CPU**: 1.0 core
- **RAM**: 1024MB
- **Ports**: 9101 (metrics), 8686 (health), 8282 (HTTP)
- **Volumes**:
  - `/mnt/ram_logs:/mnt/ram_logs:ro` (Suricata logs)
  - `vector-data:/var/lib/vector` (disk buffer)
  - `~/.aws:/root/.aws:ro` (AWS credentials)

#### 2. Redis (`ids2-redis`)
- **Image**: `redis:7-alpine`
- **Purpose**: Fallback buffer when OpenSearch unavailable
- **CPU**: 0.5 core
- **RAM**: 512MB (maxmemory: 384MB)
- **Port**: 6379
- **Volume**: `redis-data:/data` (persistence)

#### 3. Prometheus (`ids2-prometheus`)
- **Image**: `prom/prometheus:v2.48.0`
- **Purpose**: Metrics storage and querying
- **CPU**: 0.5 core
- **RAM**: 512MB
- **Port**: 9090
- **Retention**: 7 days
- **Volume**: `prometheus-data:/prometheus`

#### 4. Grafana (`ids2-grafana`)
- **Image**: `grafana/grafana:10.2.2`
- **Purpose**: Metrics visualization
- **CPU**: 0.5 core
- **RAM**: 512MB
- **Port**: 3000
- **Credentials**: admin/admin (from .env)
- **Volume**: `grafana-data:/var/lib/grafana`

### Total Resource Usage
- **CPU**: 4.0 cores total (out of 4 available)
- **RAM**: ~4GB total (out of 8GB available)
- **Headroom**: Leaves room for Suricata + system overhead

## Deployment Phases

### Phase 0: Pre-Deployment (Local Machine)

```bash
# 1. Clone repository
git clone https://github.com/alexisdeudon01/IDS.git
cd IDS

# 2. Checkout dev branch (required)
git checkout dev

# 3. Configure AWS credentials
aws configure --profile moi33
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Region: us-east-1
# Output format: json

# 4. Verify AWS access
aws sts get-caller-identity --profile moi33

# 5. Create .env file
cp .env.example .env
nano .env
# Set: OPENSEARCH_MASTER_USER, OPENSEARCH_MASTER_PASSWORD,
#      GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD
```

### Phase 1: AWS Infrastructure (Automated)

```bash
# Create OpenSearch domain
python3 deploy/create_opensearch_domain.py
```

**What happens:**
1. Creates OpenSearch domain `ids2-soc-domain`
2. Instance type: `t3.small.search`
3. Engine: OpenSearch 2.11
4. Storage: 10GB GP3
5. Region: us-east-1
6. **Waits** for domain to become active (~15 minutes)

**Output:**
- Domain endpoint (saved to config.yaml)
- Domain ARN
- Kibana endpoint

### Phase 2: Raspberry Pi Setup (Automated)

```bash
# Deploy to Raspberry Pi
./deploy/deploy_and_test.sh
```

**What happens:**

#### 2.1 File Transfer
- Uses `rsync` to copy all files to Pi
- Excludes: `.git`, `__pycache__`, `*.pyc`, documentation
- Target: `/home/pi/ids2-soc-pipeline`

#### 2.2 System Dependencies
```bash
# Installed on Pi:
- Docker (via get.docker.com)
- Docker Compose
- Python 3.9+
- pip, venv
- git, curl
```

#### 2.3 Python Environment
```bash
cd /home/pi/ids2-soc-pipeline/python_env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2.4 RAM Disk Setup
```bash
sudo ./deploy/setup_ramdisk.sh
```

Creates:
- Mount point: `/mnt/ram_logs`
- Type: tmpfs (RAM-based)
- Size: 512MB
- Persists across reboots (via /etc/fstab)

#### 2.5 Network Configuration (Optional)
```bash
sudo ./deploy/network_eth0_only.sh
```

Disables:
- wlan0 (Wi-Fi)
- usb0 (USB networking)
- Keeps: eth0 (Ethernet) - safe for SSH

### Phase 3: Docker Stack Deployment

#### 3.1 Build Agent Image
```bash
cd /home/pi/ids2-soc-pipeline
docker build -t ids2-agent:latest -f Dockerfile .
```

**Build stages:**
1. Base stage: Install build dependencies, compile Python packages
2. Production stage: Copy compiled packages, application code
3. Result: Optimized image ~500MB

#### 3.2 Pull Service Images
```bash
docker pull timberio/vector:0.34.0-debian
docker pull redis:7-alpine
docker pull prom/prometheus:v2.48.0
docker pull grafana/grafana:10.2.2
```

#### 3.3 Start Stack
```bash
docker-compose -f docker/docker-compose.yml up -d
```

**Startup order:**
1. Redis (healthcheck: `redis-cli ping`)
2. Prometheus (healthcheck: `wget http://localhost:9090/-/healthy`)
3. Vector (depends on Redis, healthcheck: `wget http://localhost:8686/health`)
4. Grafana (depends on Prometheus)
5. Agent (depends on all, manages stack)

### Phase 4: Configuration Generation

The agent (agent_mp.py) automatically generates:

#### 4.1 Vector Configuration
```bash
# Generated: vector/vector.toml
# From template: vector/vector.toml.template
```

**Includes:**
- Source: File reader for `/mnt/ram_logs/eve.json`
- Transform: Suricata JSON → ECS
- Disk buffer: 256MB at `/var/lib/vector/buffer`
- Redis sink (fallback): `redis://redis:6379/0`
- OpenSearch sink (primary): Bulk API with SigV4
- Metrics: Prometheus exporter on :9101

#### 4.2 Suricata Configuration
```bash
# Generated: suricata/suricata.yaml
# From template: suricata/suricata.yaml.template
```

**Includes:**
- Interface: eth0 (af-packet mode)
- Threads: 2 (cores 2-3)
- HOME_NET: 192.168.178.0/24
- EVE log: `/mnt/ram_logs/eve.json` (NDJSON)
- Memory caps optimized for 8GB Pi

### Phase 5: Connectivity Validation

The agent runs connectivity tests:

```python
# DNS test
await test_dns("google.com")

# TLS test
await test_tls("www.google.com", 443)

# OpenSearch bulk test
await test_opensearch_bulk_api()
```

**Timeout**: 120 seconds total for all tests

### Phase 6: Git Commit (Automated)

```bash
git add -A
git commit -m "chore(dev): agent bootstrap $(date)"
git push origin dev
```

**Requirements:**
- Must be on `dev` branch
- Git configured with author/committer
- SSH key or credentials for push

### Phase 7: Systemd Service (Optional)

```bash
# Install as system service
sudo ./deploy/enable_agent.sh

# Start service
sudo systemctl start ids2-agent

# Enable auto-start on boot
sudo systemctl enable ids2-agent

# Check status
sudo systemctl status ids2-agent

# View logs
sudo journalctl -u ids2-agent -f
```

## Verification Steps

### 1. Check Docker Containers
```bash
docker-compose -f docker/docker-compose.yml ps
```

Expected: All containers "Up" and "healthy"

### 2. Test Connectivity
```bash
./deploy/test_docker_connectivity.sh
```

Expected: All 10 tests pass ✅

### 3. Check Agent Metrics
```bash
curl http://localhost:9100/metrics | grep ids2_
```

Expected:
```
ids2_cpu_usage_percent 15.5
ids2_ram_usage_percent 42.3
ids2_throttle_level 0
ids2_pipeline_ok 1
```

### 4. Access Web Interfaces

#### Grafana (Visualization)
- URL: `http://192.168.178.66:3000`
- Username: `admin`
- Password: `admin` (from .env)
- Look for: IDS2 Dashboard

#### Prometheus (Metrics)
- URL: `http://192.168.178.66:9090`
- Navigate to: Status → Targets
- Verify: `vector` target is UP

#### Vector Health
- URL: `http://192.168.178.66:8686/health`
- Expected: `{"status":"healthy"}`

### 5. Test End-to-End Pipeline

```bash
# Send a test event
echo '{"timestamp":"2026-02-01T10:00:00Z","event_type":"test","message":"E2E test"}' \
  | curl -X POST -H "Content-Type: application/json" -d @- \
  http://localhost:8282/

# Check Vector metrics for processed events
curl http://localhost:9101/metrics | grep vector_component_received_events_total
```

## Troubleshooting

### Issue: Docker build fails

**Solution:**
```bash
# Clear Docker cache
docker system prune -a

# Rebuild with no cache
docker build --no-cache -t ids2-agent:latest -f Dockerfile .
```

### Issue: Container unhealthy

**Check logs:**
```bash
docker logs ids2-<service>
```

**Restart container:**
```bash
docker-compose -f docker/docker-compose.yml restart <service>
```

### Issue: OpenSearch 403 Forbidden

**Cause:** FGAC not configured

**Solution:**
1. Login to OpenSearch Dashboards
2. Navigate to: Security → Roles
3. Map IAM ARN to `all_access` role:
   ```json
   {
     "backend_roles": [],
     "hosts": [],
     "users": ["arn:aws:iam::211125764416:user/alexis"]
   }
   ```

### Issue: Agent won't start

**Check systemd logs:**
```bash
sudo journalctl -u ids2-agent -n 50 --no-pager
```

**Common causes:**
- AWS credentials not configured
- Docker daemon not running
- RAM disk not mounted
- Config file missing

### Issue: High CPU/RAM usage

**Check throttle level:**
```bash
curl http://localhost:9100/metrics | grep throttle_level
```

**If level > 0:**
- Reduce Suricata threads in config.yaml
- Reduce Vector batch size
- Add more RAM disk space

## File Structure After Deployment

```
/home/pi/ids2-soc-pipeline/
├── config.yaml                      # Main configuration
├── .env                            # Secrets (not in git)
├── Dockerfile                      # Agent container build
│
├── python_env/
│   ├── agent_mp.py                 # Main orchestrator
│   ├── venv/                       # Python virtual environment
│   ├── requirements.txt
│   └── modules/                    # Agent modules
│
├── docker/
│   ├── docker-compose.yml          # Service orchestration
│   ├── prometheus.yml              # Prometheus config
│   └── grafana/                    # Grafana provisioning
│
├── vector/
│   ├── vector.toml.template        # Template
│   └── vector.toml                 # Generated config
│
├── suricata/
│   ├── suricata.yaml.template      # Template
│   └── suricata.yaml               # Generated config
│
└── deploy/
    ├── deploy_and_test.sh          # Master deployment script
    ├── setup_ramdisk.sh            # RAM disk setup
    ├── network_eth0_only.sh        # Network lockdown
    ├── ids2-agent.service          # Systemd unit
    ├── enable_agent.sh             # Service installer
    ├── start_agent.sh              # Service starter
    ├── stop_agent.sh               # Service stopper
    ├── reset.sh                    # Full cleanup
    └── test_docker_connectivity.sh # Connectivity tests
```

## Resource Monitoring

### Real-time Monitoring
```bash
# Watch Docker stats
docker stats

# Watch agent metrics
watch -n 2 'curl -s http://localhost:9100/metrics | grep ids2_'

# Watch system resources
htop
```

### Prometheus Queries (in UI)

```promql
# CPU usage over time
ids2_cpu_usage_percent

# RAM usage over time
ids2_ram_usage_percent

# Throttle level (should be 0)
ids2_throttle_level

# Pipeline health (should be 1)
ids2_pipeline_ok

# Vector throughput
rate(vector_component_sent_events_total[1m])
```

## Updating the Deployment

```bash
# 1. Pull latest changes
git pull origin dev

# 2. Rebuild agent image
docker build -t ids2-agent:latest -f Dockerfile .

# 3. Restart stack
docker-compose -f docker/docker-compose.yml down
docker-compose -f docker/docker-compose.yml up -d

# 4. Verify
./deploy/test_docker_connectivity.sh
```

## Complete Reset

To completely remove everything and start fresh:

```bash
sudo ./deploy/reset.sh
```

This removes:
- All Docker containers and volumes
- Python virtual environment
- Generated configurations
- Systemd service
- RAM disk (optional)

## Next Steps

After successful deployment:

1. ✅ Configure Suricata rules
2. ✅ Create Grafana dashboards
3. ✅ Set up alerting in Prometheus
4. ✅ Configure OpenSearch index templates
5. ✅ Test with real traffic
6. ✅ Document playbooks for incident response

## Support

For issues or questions:
- Check `DOCKER_CONNECTIVITY.md` for connectivity issues
- Check `TESTING_GUIDE.md` for test procedures
- Check agent logs: `sudo journalctl -u ids2-agent -f`
- Check container logs: `docker logs ids2-<service>`
