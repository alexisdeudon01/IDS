# IDS2 SOC Pipeline - Raspberry Pi 5

A production-ready, resource-optimized Security Operations Center (SOC) pipeline for Raspberry Pi 5, featuring network intrusion detection, log ingestion, and real-time monitoring.

![Architecture](https://img.shields.io/badge/Architecture-Multi--Process-blue)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Development](#development)
- [License](#license)

---

## 🎯 Overview

The IDS2 SOC Pipeline is a complete security monitoring solution designed specifically for Raspberry Pi 5. It combines:

- **Suricata** - Network Intrusion Detection System (NIDS)
- **Vector** - High-performance log ingestion and transformation
- **AWS OpenSearch** - Centralized log storage and search
- **Redis** - Fallback buffer for reliability
- **Prometheus** - Metrics collection
- **Grafana** - Real-time visualization
- **Python Multi-Process Agent** - Orchestration and resource management

### Key Highlights

✅ **Resource-Aware**: Enforces strict CPU/RAM limits (≤70%)  
✅ **Auto-Throttling**: 4-level throttling system prevents resource exhaustion  
✅ **High Performance**: RAM disk for logs, optimized for ARM64  
✅ **Production-Ready**: Graceful shutdown, auto-restart, comprehensive logging  
✅ **ECS-Compliant**: Elastic Common Schema for standardized log format  
✅ **Fully Automated**: One-command deployment with health checks  

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RASPBERRY PI 5 (8GB RAM, 4 cores)           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Network Traffic (eth0 ONLY)                             │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                             │
│                   ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SURICATA (2 threads, af-packet)                         │  │
│  │  - Network IDS                                           │  │
│  │  - EVE JSON output                                       │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                             │
│                   ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  RAM DISK (/mnt/ram_logs - 512MB tmpfs)                  │  │
│  │  - eve.json (Suricata logs)                              │  │
│  │  - High-speed I/O                                        │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                             │
│                   ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  VECTOR (1 core, 1GB RAM)                                │  │
│  │  - Read & parse logs                                     │  │
│  │  - Transform to ECS                                      │  │
│  │  - Bulk batching (100 events)                            │  │
│  └────────────────┬─────────────────────────────────────────┘  │
│                   │                                             │
│         ┌─────────┴─────────┐                                  │
│         ▼                   ▼                                  │
│  ┌─────────────┐     ┌─────────────┐                          │
│  │ DISK BUFFER │     │   REDIS     │                          │
│  │  (256MB)    │     │  (Fallback) │                          │
│  └──────┬──────┘     └──────┬──────┘                          │
│         │                   │                                  │
│         └─────────┬─────────┘                                  │
│                   ▼                                             │
└───────────────────┼─────────────────────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  AWS OPENSEARCH      │
         │  - Bulk ingestion    │
         │  - Daily indices     │
         │  - ECS format        │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │     GRAFANA          │
         │  - Visualization     │
         │  - Dashboards        │
         │  - Alerting          │
         └──────────────────────┘
```

### Multi-Process Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Process #1: SUPERVISOR (agent_mp.py)                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  • Spawns all child processes                           │
│  • Monitors liveness                                    │
│  • Handles SIGINT/SIGTERM                               │
│  • Orchestrates shutdown sequence                       │
│  • Runs deployment phases A-G                           │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┬──────────────┐
        ▼                 ▼                 ▼              ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐
│ Process #2    │ │ Process #3   │ │ Process #4   │ │ Process #5  │
│ ━━━━━━━━━━━━━ │ │ ━━━━━━━━━━━━ │ │ ━━━━━━━━━━━━ │ │ ━━━━━━━━━━━ │
│ RESOURCE      │ │ CONNECTIVITY │ │ METRICS      │ │ VERIFICATION│
│ CONTROLLER    │ │ (async)      │ │ SERVER       │ │ (optional)  │
│               │ │              │ │              │ │             │
│ • CPU monitor │ │ • DNS check  │ │ • Prom :9100 │ │ • Query OS  │
│ • RAM monitor │ │ • TLS check  │ │ • Expose     │ │ • Verify    │
│ • Throttling  │ │ • Bulk test  │ │   metrics    │ │   ingestion │
│ • GC trigger  │ │ • uvloop     │ │ • 5s update  │ │ • Alert on  │
│ • 2s interval │ │ • 30s check  │ │              │ │   stall     │
└───────────────┘ └──────────────┘ └──────────────┘ └─────────────┘
```

### Deployment Phases

```
Phase A: AWS Verification
  ├─ Verify credentials (boto3 + profile 'moi33')
  ├─ Check OpenSearch domain exists
  └─ Get domain endpoint

Phase B: Configuration Generation
  ├─ Generate suricata.yaml (optimized for Pi5)
  ├─ Validate Suricata config
  ├─ Generate vector.toml (ECS-compliant)
  └─ Validate Vector config

Phase C: Docker Stack Deployment
  ├─ Verify docker-compose.yml
  ├─ Pull images
  ├─ Start services (Vector, Redis, Prometheus, Grafana)
  └─ Wait for health checks

Phase D: Connectivity Verification
  ├─ Wait for DNS resolution
  ├─ Wait for TLS handshake
  └─ Wait for OpenSearch bulk test

Phase E: Pipeline Verification
  ├─ Check all services running
  ├─ Check AWS connectivity
  ├─ Check resource usage
  └─ Set pipeline_ok = true

Phase F: Git Commit
  ├─ Stage all changes (git add -A)
  ├─ Commit with message
  └─ Push to origin/dev

Phase G: Monitoring Loop
  ├─ Monitor child processes
  ├─ Restart crashed processes
  ├─ Log status every 30s
  └─ Wait for shutdown signal
```

---

## ✨ Features

### Resource Management

- **CPU/RAM Monitoring**: Real-time monitoring with 2-second intervals
- **4-Level Throttling**:
  - Level 0 (< 50%): Full speed
  - Level 1 (50-60%): Light throttling (1.5x sleep)
  - Level 2 (60-70%): Medium throttling (2x sleep, half batch)
  - Level 3 (> 70%): Heavy throttling (4x sleep, quarter batch)
- **Automatic GC**: Forced garbage collection when RAM > 65%
- **Hard Limits**: Enforces ≤70% CPU/RAM (NON-NEGOTIABLE)

### Connectivity

- **Async Checks**: DNS, TLS, OpenSearch bulk (concurrent with uvloop)
- **Retry Logic**: Exponential backoff (2s → 10s)
- **Timeout Handling**: 10s DNS, 10s TLS, 30s bulk
- **Health Monitoring**: 30-second check intervals

### Metrics & Monitoring

- **Prometheus Exporter**: Port 9100 (0.0.0.0)
- **System Metrics**: CPU, RAM, throttle level
- **Connectivity Metrics**: DNS, TLS, OpenSearch status
- **Pipeline Metrics**: Vector, Suricata, Redis status
- **Grafana Dashboards**: Pre-configured visualization

### Data Pipeline

- **ECS Transformation**: Elastic Common Schema compliance
- **Bulk Batching**: 100 events, 30s timeout
- **Disk Buffer**: 256MB for reliability
- **Redis Fallback**: Secondary buffer layer
- **Compression**: gzip for network efficiency

---

## 📦 Requirements

### Hardware

- **Raspberry Pi 5** (8GB RAM recommended)
- **MicroSD Card**: 64GB+ (Class 10 or better)
- **Network**: Ethernet connection (eth0)
- **Power**: Official Raspberry Pi 5 power supply

### Software

- **OS**: Debian GNU/Linux 13 (Trixie) or Ubuntu 22.04+
- **Python**: 3.11 or higher
- **Docker**: 24.0+ with Docker Compose
- **Suricata**: 7.0+ (will be installed)
- **Git**: For version control

### AWS

- **AWS Account** with OpenSearch domain
- **IAM Credentials** configured in profile 'moi33'
- **OpenSearch Domain**: Running and accessible
- **Network Access**: Raspberry Pi can reach OpenSearch endpoint

---

## 🚀 Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/your-repo/ids2-soc-pipeline.git
cd ids2-soc-pipeline
```

### Step 2: Install System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get install docker-compose -y

# Install Suricata
sudo apt-get install suricata -y

# Install Python dependencies
sudo apt-get install python3-pip python3-venv -y
```

### Step 3: Setup Python Environment

```bash
cd python_env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Configure AWS Credentials

```bash
# Install AWS CLI
pip install awscli

# Configure profile 'moi33'
aws configure --profile moi33
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region (e.g., us-east-1)
# Enter output format (json)
```

### Step 5: Edit Configuration

```bash
# Edit config.yaml
nano config.yaml

# Update these fields:
# - aws.opensearch_domain: Your OpenSearch domain name
# - aws.opensearch_endpoint: Your OpenSearch endpoint (or leave blank for auto-detect)
# - raspberry_pi.ip_address: Your Pi's IP address
# - raspberry_pi.network_interface: Should be 'eth0'
```

### Step 6: Setup RAM Disk

```bash
# Create RAM disk for high-performance logging
sudo ./deploy/setup_ramdisk.sh
```

### Step 7: Configure Network (Optional but Recommended)

```bash
# Disable all network interfaces except eth0
sudo ./deploy/network_eth0_only.sh
```

### Step 8: Install as System Service

```bash
# Install and enable systemd service
sudo ./deploy/enable_agent.sh
```

---

## ⚙️ Configuration

### Main Configuration File: `config.yaml`

```yaml
# Resource Limits (NON-NEGOTIABLE)
resources:
  max_cpu_percent: 70.0
  max_ram_percent: 70.0
  throttle_threshold_1: 50.0
  throttle_threshold_2: 60.0
  throttle_threshold_3: 70.0

# AWS Configuration
aws:
  profile: "moi33"
  region: "us-east-1"
  opensearch_domain: "ids2-soc-domain"
  opensearch_endpoint: ""  # Auto-detected
  index_prefix: "ids2-logs"
  bulk_size: 100
  bulk_timeout: 30

# Network Configuration
raspberry_pi:
  ip_address: "192.168.178.66"
  network_interface: "eth0"
```

### Vector Configuration: `vector/vector.toml`

Auto-generated by the agent. Key settings:

- **Source**: `/mnt/ram_logs/eve.json`
- **Batch Size**: 100 events
- **Timeout**: 30 seconds
- **Buffer**: 256MB disk buffer
- **Fallback**: Redis buffer

### Suricata Configuration: `suricata/suricata.yaml`

Auto-generated by the agent. Key settings:

- **Threads**: 2 worker threads
- **CPU Affinity**: Cores 2-3
- **Memory**: 512MB total
- **Output**: `/mnt/ram_logs/eve.json`

---

## 🎮 Usage

### Start the Agent

```bash
# Using systemd (recommended)
sudo systemctl start ids2-agent

# Or run directly
python3 python_env/agent_mp.py
```

### Stop the Agent

```bash
# Using systemd
sudo systemctl stop ids2-agent

# Or use stop script
sudo ./deploy/stop_agent.sh
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u ids2-agent -f

# Last 100 lines
sudo journalctl -u ids2-agent -n 100

# Logs since boot
sudo journalctl -u ids2-agent -b
```

### Check Status

```bash
# Service status
sudo systemctl status ids2-agent

# Docker services
docker-compose -f docker/docker-compose.yml ps

# Resource usage
htop
```

### Reset Everything

```bash
# Complete reset (stops all, removes containers, clears logs)
sudo ./deploy/reset.sh
```

---

## 📊 Monitoring

### Prometheus Metrics

Access metrics at: `http://192.168.178.66:9100/metrics`

Key metrics:
- `ids2_cpu_usage_percent` - Current CPU usage
- `ids2_ram_usage_percent` - Current RAM usage
- `ids2_throttle_level` - Current throttle level (0-3)
- `ids2_dns_status` - DNS connectivity (0/1)
- `ids2_tls_status` - TLS connectivity (0/1)
- `ids2_opensearch_status` - OpenSearch connectivity (0/1)
- `ids2_pipeline_ok` - Overall pipeline health (0/1)

### Grafana Dashboard

Access Grafana at: `http://192.168.178.66:3000`

- **Username**: admin
- **Password**: admin (change on first login)

Pre-configured dashboard shows:
- CPU/RAM gauges with thresholds
- Throttle level over time
- Service status indicators
- Connectivity status

### Prometheus UI

Access Prometheus at: `http://192.168.178.66:9090`

Query examples:
```promql
# CPU usage over time
ids2_cpu_usage_percent

# RAM usage over time
ids2_ram_usage_percent

# Throttle events
changes(ids2_throttle_level[5m])
```

---

## 🔧 Troubleshooting

### Agent Won't Start

```bash
# Check logs
sudo journalctl -u ids2-agent -n 50

# Common issues:
# 1. AWS credentials not configured
aws configure --profile moi33

# 2. Docker not running
sudo systemctl start docker

# 3. RAM disk not mounted
sudo ./deploy/setup_ramdisk.sh

# 4. Port conflicts
sudo netstat -tulpn | grep -E '9100|9090|3000|6379'
```

### High Resource Usage

```bash
# Check current usage
htop

# Check throttle level
curl http://localhost:9100/metrics | grep throttle_level

# If throttle level is 3:
# - Reduce Suricata threads in config.yaml
# - Reduce Vector batch size
# - Check for memory leaks
```

### OpenSearch Connection Issues

```bash
# Test DNS resolution
dig your-opensearch-domain.us-east-1.es.amazonaws.com

# Test TLS connection
openssl s_client -connect your-opensearch-domain.us-east-1.es.amazonaws.com:443

# Test bulk API
curl -X POST "https://your-opensearch-domain/_bulk" \
  -H "Content-Type: application/x-ndjson" \
  --aws-sigv4 "aws:amz:us-east-1:es" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY"
```

### Docker Services Not Starting

```bash
# Check Docker daemon
sudo systemctl status docker

# Check compose file
docker-compose -f docker/docker-compose.yml config

# Pull images manually
docker-compose -f docker/docker-compose.yml pull

# Check logs
docker-compose -f docker/docker-compose.yml logs
```

### Suricata Not Capturing Traffic

```bash
# Check interface
ip link show eth0

# Check Suricata is running
ps aux | grep suricata

# Check Suricata logs
sudo tail -f /var/log/suricata/suricata.log

# Check EVE JSON output
sudo tail -f /mnt/ram_logs/eve.json
```

---

## ⚡ Performance Tuning

### For Lower Resource Usage

Edit `config.yaml`:

```yaml
resources:
  max_cpu_percent: 60.0  # Lower limit
  max_ram_percent: 60.0  # Lower limit

suricata:
  threads: 1  # Reduce threads
  detect_profile: "low"  # Lower detection

vector:
  batch_max_events: 50  # Smaller batches
```

### For Higher Performance

Edit `config.yaml`:

```yaml
resources:
  max_cpu_percent: 80.0  # Higher limit (not recommended)
  max_ram_percent: 80.0  # Higher limit (not recommended)

suricata:
  threads: 3  # More threads
  detect_profile: "high"  # Higher detection

vector:
  batch_max_events: 200  # Larger batches
```

### Optimize RAM Disk

```bash
# Increase RAM disk size (if you have RAM to spare)
sudo umount /mnt/ram_logs
sudo mount -t tmpfs -o size=1G,mode=1777 tmpfs /mnt/ram_logs

# Update /etc/fstab
sudo nano /etc/fstab
# Change size=512M to size=1G
```

---

## 🛠️ Development

### Project Structure

```
ids2-soc-pipeline/
├── config.yaml                 # Master configuration
├── python_env/
│   ├── agent_mp.py            # Main orchestrator
│   ├── requirements.txt       # Python dependencies
│   └── modules/
│       ├── config_manager.py
│       ├── resource_controller.py
│       ├── connectivity_async.py
│       ├── metrics_server.py
│       ├── aws_manager.py
│       ├── docker_manager.py
│       ├── vector_manager.py
│       ├── suricata_manager.py
│       └── git_workflow.py
├── docker/
│   ├── docker-compose.yml
│   ├── prometheus.yml
│   └── grafana/
├── vector/
│   └── vector.toml            # Auto-generated
├── suricata/
│   └── suricata.yaml          # Auto-generated
└── deploy/
    ├── ids2-agent.service
    ├── enable_agent.sh
    ├── start_agent.sh
    ├── stop_agent.sh
    ├── reset.sh
    ├── setup_ramdisk.sh
    └── network_eth0_only.sh
```

### Running Tests

```bash
# Test configuration loading
python3 -c "from modules.config_manager import ConfigManager; c = ConfigManager(); print('OK')"

# Test AWS connectivity
python3 -c "from modules.aws_manager import AWSManager; from modules.config_manager import ConfigManager; a = AWSManager(ConfigManager()); print(a.verify_credentials())"

# Test Docker
docker-compose -f docker/docker-compose.yml config
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **Suricata** - Open Source IDS/IPS
- **Vector** - High-performance observability data pipeline
- **AWS OpenSearch** - Managed Elasticsearch service
- **Prometheus** - Monitoring and alerting toolkit
- **Grafana** - Analytics and monitoring platform

---

## 📞 Support

For issues, questions, or contributions:

- **GitHub Issues**: [Create an issue](https://github.com/your-repo/ids2-soc-pipeline/issues)
- **Documentation**: [Wiki](https://github.com/your-repo/ids2-soc-pipeline/wiki)
- **Email**: support@example.com

---

**Built with ❤️ for Raspberry Pi 5**
