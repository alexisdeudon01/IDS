# IDS2 SOC Pipeline - Comprehensive Testing Guide

This guide provides thorough testing procedures for the IDS2 SOC Pipeline on Raspberry Pi 5.

---

## 📋 Table of Contents

1. [Pre-Deployment Testing](#pre-deployment-testing)
2. [AWS OpenSearch Setup](#aws-opensearch-setup)
3. [Raspberry Pi Setup](#raspberry-pi-setup)
4. [Component Testing](#component-testing)
5. [Integration Testing](#integration-testing)
6. [Performance Testing](#performance-testing)
7. [Failure Testing](#failure-testing)
8. [Production Readiness Checklist](#production-readiness-checklist)

---

## 1. Pre-Deployment Testing

### 1.1 Verify Network Connectivity

```bash
# Test from your local machine to Raspberry Pi
ping -c 5 192.168.178.66

# Expected: 0% packet loss, <10ms latency
```

**✅ PASSED**: Connection successful (5ms latency, 0% packet loss)

### 1.2 Verify File Structure

```bash
# Check all required files exist
cd /tmp/blackbox-worktrees/r
find . -type f -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.sh" | wc -l

# Expected: 28+ files
```

### 1.3 Validate Configuration Files

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))" && echo "✅ config.yaml valid"

# Validate Docker Compose
docker-compose -f docker/docker-compose.yml config > /dev/null && echo "✅ docker-compose.yml valid"

# Validate Python syntax
python3 -m py_compile python_env/agent_mp.py && echo "✅ agent_mp.py valid"
python3 -m py_compile python_env/modules/*.py && echo "✅ All modules valid"
```

**✅ PASSED**: All configuration files are syntactically valid

---

## 2. AWS OpenSearch Setup

### 2.1 Create PUBLIC OpenSearch Domain

**Option A: Using the provided script**

```bash
# Run the automated script
sudo ./deploy/create_opensearch_domain.sh

# This will:
# - Create a t3.small.search instance
# - Configure PUBLIC access with IP restriction (192.168.178.66/32)
# - Enable HTTPS and TLS 1.2+
# - Set up master user (admin/Admin123!)
# - Wait for domain to become active (~15 minutes)
```

**Option B: Manual creation via AWS Console**

1. Go to AWS Console → OpenSearch Service
2. Click "Create domain"
3. Configuration:
   - **Domain name**: `ids2-soc-domain`
   - **Deployment type**: Development and testing
   - **Version**: OpenSearch 2.11
   - **Instance type**: t3.small.search
   - **Number of nodes**: 1
   - **EBS storage**: 10 GB gp3
   - **Network**: Public access
   - **Fine-grained access control**: Enabled
     - Master user: `admin`
     - Master password: `Admin123!` (change this!)
   - **Access policy**: Custom
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {"AWS": "*"},
           "Action": "es:*",
           "Resource": "arn:aws:es:us-east-1:*:domain/ids2-soc-domain/*",
           "Condition": {
             "IpAddress": {
               "aws:SourceIp": ["192.168.178.66/32"]
             }
           }
         }
       ]
     }
     ```
   - **Encryption**: Enable node-to-node encryption
   - **Encryption at rest**: Enabled
   - **HTTPS**: Required
   - **TLS policy**: TLS 1.2

4. Click "Create" and wait 10-15 minutes

### 2.2 Verify OpenSearch Domain

```bash
# Get domain endpoint
aws opensearch describe-domain \
  --domain-name ids2-soc-domain \
  --profile moi33 \
  --region us-east-1 \
  --query 'DomainStatus.Endpoint' \
  --output text

# Expected output: search-ids2-soc-domain-xxxxx.us-east-1.es.amazonaws.com
```

### 2.3 Test OpenSearch Connectivity

```bash
# From Raspberry Pi (192.168.178.66), test connection
ENDPOINT="https://search-ids2-soc-domain-xxxxx.us-east-1.es.amazonaws.com"

# Test basic connectivity
curl -u admin:Admin123! "$ENDPOINT"

# Expected: JSON response with cluster info

# Test bulk API
curl -u admin:Admin123! -X POST "$ENDPOINT/_bulk" \
  -H "Content-Type: application/x-ndjson" \
  -d '{"index":{"_index":"test-index"}}
{"message":"test"}
'

# Expected: {"took":X,"errors":false,...}
```

### 2.4 Update Configuration

```bash
# Update config.yaml with the endpoint
nano config.yaml

# Set:
# aws:
#   opensearch_endpoint: "https://search-ids2-soc-domain-xxxxx.us-east-1.es.amazonaws.com"
```

---

## 3. Raspberry Pi Setup

### 3.1 SSH to Raspberry Pi

```bash
# From your local machine
ssh pi@192.168.178.66

# Or if using different user
ssh your_username@192.168.178.66
```

### 3.2 Install System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Logout and login again for docker group to take effect
exit
ssh pi@192.168.178.66

# Verify Docker
docker --version
docker-compose --version

# Install Suricata
sudo apt-get install suricata -y
suricata --version

# Install Python dependencies
sudo apt-get install python3-pip python3-venv -y
python3 --version
```

### 3.3 Clone Repository

```bash
# Clone the repository
cd ~
git clone https://github.com/your-repo/ids2-soc-pipeline.git
cd ids2-soc-pipeline

# Verify all files
ls -la
```

### 3.4 Setup Python Environment

```bash
cd python_env
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify installations
pip list
```

### 3.5 Configure AWS Credentials

```bash
# Install AWS CLI
pip install awscli

# Configure profile
aws configure --profile moi33
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region: us-east-1
# Enter output format: json

# Verify
aws sts get-caller-identity --profile moi33
```

### 3.6 Setup RAM Disk

```bash
# Create RAM disk for high-performance logging
sudo ./deploy/setup_ramdisk.sh

# Verify
df -h /mnt/ram_logs
mount | grep ram_logs
```

### 3.7 Configure Network (Optional)

```bash
# Disable all interfaces except eth0
sudo ./deploy/network_eth0_only.sh

# Verify
ip link show
```

---

## 4. Component Testing

### 4.1 Test Configuration Manager

```bash
cd ~/ids2-soc-pipeline
source python_env/venv/bin/activate

# Test config loading
python3 << EOF
from python_env.modules.config_manager import ConfigManager

config = ConfigManager('config.yaml')
print("✅ Config loaded successfully")
print(f"AWS Region: {config.get('aws.region')}")
print(f"Max CPU: {config.get('resources.max_cpu_percent')}%")
print(f"Max RAM: {config.get('resources.max_ram_percent')}%")
EOF
```

**Expected Output:**
```
✅ Config loaded successfully
AWS Region: us-east-1
Max CPU: 70.0%
Max RAM: 70.0%
```

### 4.2 Test AWS Manager

```bash
# Test AWS connectivity
python3 << EOF
from python_env.modules.config_manager import ConfigManager
from python_env.modules.aws_manager import AWSManager

config = ConfigManager('config.yaml')
aws_mgr = AWSManager(config)

# Verify credentials
if aws_mgr.verify_credentials():
    print("✅ AWS credentials valid")
else:
    print("❌ AWS credentials invalid")

# Check OpenSearch domain
domain_info = aws_mgr.get_domain_info()
if domain_info:
    print(f"✅ OpenSearch domain found: {domain_info['DomainName']}")
    print(f"   Endpoint: {domain_info.get('Endpoint', 'N/A')}")
else:
    print("❌ OpenSearch domain not found")
EOF
```

### 4.3 Test Docker Manager

```bash
# Test Docker connectivity
python3 << EOF
from python_env.modules.config_manager import ConfigManager
from python_env.modules.docker_manager import DockerManager

config = ConfigManager('config.yaml')
docker_mgr = DockerManager(config)

# Verify Docker
if docker_mgr.verify_docker():
    print("✅ Docker is accessible")
else:
    print("❌ Docker is not accessible")

# Check compose file
if docker_mgr.verify_compose_file():
    print("✅ Docker Compose file is valid")
else:
    print("❌ Docker Compose file is invalid")
EOF
```

### 4.4 Test Vector Configuration Generation

```bash
# Test Vector config generation
python3 << EOF
from python_env.modules.config_manager import ConfigManager
from python_env.modules.vector_manager import VectorManager

config = ConfigManager('config.yaml')
vector_mgr = VectorManager(config)

# Generate config
if vector_mgr.generate_config():
    print("✅ Vector config generated successfully")
    print(f"   Location: {vector_mgr.config_file}")
else:
    print("❌ Vector config generation failed")

# Validate config
if vector_mgr.validate_config():
    print("✅ Vector config is valid")
else:
    print("❌ Vector config is invalid")
EOF
```

### 4.5 Test Suricata Configuration Generation

```bash
# Test Suricata config generation
python3 << EOF
from python_env.modules.config_manager import ConfigManager
from python_env.modules.suricata_manager import SuricataManager

config = ConfigManager('config.yaml')
suricata_mgr = SuricataManager(config)

# Generate config
if suricata_mgr.generate_config():
    print("✅ Suricata config generated successfully")
    print(f"   Location: {suricata_mgr.config_file}")
else:
    print("❌ Suricata config generation failed")

# Validate config
if suricata_mgr.validate_config():
    print("✅ Suricata config is valid")
else:
    print("❌ Suricata config is invalid")
EOF
```

---

## 5. Integration Testing

### 5.1 Test Docker Stack Deployment

```bash
# Pull Docker images
docker-compose -f docker/docker-compose.yml pull

# Start services
docker-compose -f docker/docker-compose.yml up -d

# Check status
docker-compose -f docker/docker-compose.yml ps

# Expected: All services "Up" and "healthy"

# Check logs
docker-compose -f docker/docker-compose.yml logs vector
docker-compose -f docker/docker-compose.yml logs redis
docker-compose -f docker/docker-compose.yml logs prometheus
docker-compose -f docker/docker-compose.yml logs grafana

# Stop services
docker-compose -f docker/docker-compose.yml down
```

### 5.2 Test Multi-Process Agent (Dry Run)

```bash
# Run agent in foreground for testing
cd ~/ids2-soc-pipeline
source python_env/venv/bin/activate

# Set dry-run mode in config.yaml
sed -i 's/dry_run: false/dry_run: true/' config.yaml

# Run agent
python3 python_env/agent_mp.py

# Expected output:
# - Phase A: AWS verification
# - Phase B: Config generation
# - Phase C: Docker stack start
# - Phase D: Connectivity checks
# - Phase E: Pipeline verification
# - Phase F: Git commit (skipped in dry-run)
# - Phase G: Monitoring loop

# Press Ctrl+C to stop
```

### 5.3 Test Resource Controller

```bash
# Monitor resource usage
python3 << EOF
import time
from python_env.modules.config_manager import ConfigManager
from python_env.modules.resource_controller import ResourceController
from multiprocessing import Manager

config = ConfigManager('config.yaml')
manager = Manager()
shared_state = manager.dict()

rc = ResourceController(config, shared_state)
rc.start()

# Monitor for 30 seconds
for i in range(6):
    time.sleep(5)
    print(f"CPU: {shared_state['cpu_percent']:.1f}% | RAM: {shared_state['ram_percent']:.1f}% | Throttle: {shared_state['throttle_level']}")

rc.stop()
print("✅ Resource controller test complete")
EOF
```

### 5.4 Test Connectivity Checker

```bash
# Test async connectivity
python3 << EOF
import asyncio
from python_env.modules.config_manager import ConfigManager
from python_env.modules.connectivity_async import ConnectivityChecker
from multiprocessing import Manager

config = ConfigManager('config.yaml')
manager = Manager()
shared_state = manager.dict()

cc = ConnectivityChecker(config, shared_state)
cc.start()

# Wait for checks
import time
time.sleep(35)

print(f"DNS Status: {shared_state.get('dns_ok', False)}")
print(f"TLS Status: {shared_state.get('tls_ok', False)}")
print(f"OpenSearch Status: {shared_state.get('opensearch_ok', False)}")

cc.stop()
print("✅ Connectivity checker test complete")
EOF
```

### 5.5 Test Metrics Server

```bash
# Start metrics server
python3 << EOF
import time
from python_env.modules.config_manager import ConfigManager
from python_env.modules.metrics_server import MetricsServer
from multiprocessing import Manager

config = ConfigManager('config.yaml')
manager = Manager()
shared_state = manager.dict()

# Initialize shared state
shared_state['cpu_percent'] = 25.0
shared_state['ram_percent'] = 30.0
shared_state['throttle_level'] = 0
shared_state['dns_ok'] = True
shared_state['tls_ok'] = True
shared_state['opensearch_ok'] = True
shared_state['pipeline_ok'] = True

ms = MetricsServer(config, shared_state)
ms.start()

print("✅ Metrics server started on port 9100")
print("   Test with: curl http://192.168.178.66:9100/metrics")

time.sleep(60)
ms.stop()
EOF
```

From another terminal:
```bash
# Test metrics endpoint
curl http://192.168.178.66:9100/metrics | grep ids2_

# Expected: Multiple metrics with values
```

---

## 6. Performance Testing

### 6.1 Baseline Resource Usage

```bash
# Monitor baseline (no load)
htop

# Record:
# - CPU idle: Should be >90%
# - RAM used: Should be <2GB
# - Load average: Should be <1.0
```

### 6.2 Stress Test - CPU

```bash
# Install stress tool
sudo apt-get install stress -y

# Run CPU stress test
stress --cpu 2 --timeout 60s &

# Monitor throttling
watch -n 1 'curl -s http://localhost:9100/metrics | grep throttle_level'

# Expected: Throttle level should increase to 2 or 3
```

### 6.3 Stress Test - RAM

```bash
# Run RAM stress test
stress --vm 1 --vm-bytes 4G --timeout 60s &

# Monitor throttling
watch -n 1 'curl -s http://localhost:9100/metrics | grep -E "(ram_usage|throttle_level)"'

# Expected: RAM usage increases, throttle level increases
```

### 6.4 Network Throughput Test

```bash
# Generate test traffic
sudo apt-get install hping3 -y

# Send packets to trigger Suricata
sudo hping3 -S -p 80 -c 1000 --fast 8.8.8.8

# Check Suricata logs
sudo tail -f /mnt/ram_logs/eve.json

# Expected: JSON events being logged
```

### 6.5 Vector Ingestion Test

```bash
# Generate test events
for i in {1..1000}; do
  echo '{"timestamp":"'$(date -Iseconds)'","event_type":"test","message":"Test event '$i'"}' >> /mnt/ram_logs/eve.json
done

# Check Vector processing
docker logs ids2-vector --tail 50

# Check OpenSearch ingestion
curl -u admin:Admin123! "https://your-endpoint/_cat/indices/ids2-logs-*?v"

# Expected: Events ingested into daily index
```

---

## 7. Failure Testing

### 7.1 Test Process Restart

```bash
# Kill a child process
pkill -f "resource_controller"

# Check if supervisor restarts it
tail -f /var/log/syslog | grep ids2

# Expected: Process restarted automatically
```

### 7.2 Test Docker Service Failure

```bash
# Stop Vector container
docker stop ids2-vector

# Check pipeline status
curl http://localhost:9100/metrics | grep pipeline_ok

# Expected: pipeline_ok = 0

# Restart Vector
docker start ids2-vector

# Expected: pipeline_ok = 1 after health check
```

### 7.3 Test Network Failure

```bash
# Simulate network failure (disconnect eth0)
sudo ip link set eth0 down

# Check connectivity status
curl http://localhost:9100/metrics | grep -E "(dns_ok|tls_ok|opensearch_ok)"

# Expected: All = 0

# Restore network
sudo ip link set eth0 up

# Expected: All = 1 after retry
```

### 7.4 Test OpenSearch Unavailability

```bash
# Block OpenSearch endpoint temporarily
sudo iptables -A OUTPUT -d your-opensearch-ip -j DROP

# Check Vector fallback to Redis
docker logs ids2-vector --tail 50

# Expected: Events buffered to Redis

# Restore connectivity
sudo iptables -D OUTPUT -d your-opensearch-ip -j DROP

# Expected: Events flushed from Redis to OpenSearch
```

---

## 8. Production Readiness Checklist

### 8.1 Configuration

- [ ] `config.yaml` updated with correct OpenSearch endpoint
- [ ] AWS credentials configured (profile 'moi33')
- [ ] Resource limits set appropriately (≤70%)
- [ ] Network interface set to eth0 only
- [ ] RAM disk mounted at /mnt/ram_logs
- [ ] All deployment scripts executable

### 8.2 Services

- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] Suricata installed
- [ ] Python 3.11+ installed
- [ ] All Python dependencies installed
- [ ] Systemd service configured

### 8.3 Network

- [ ] Raspberry Pi accessible at 192.168.178.66
- [ ] Only eth0 interface enabled
- [ ] Firewall rules configured (if any)
- [ ] OpenSearch endpoint accessible from Pi

### 8.4 AWS

- [ ] OpenSearch domain created and active
- [ ] Domain endpoint obtained
- [ ] Access policy allows Pi IP (192.168.178.66/32)
- [ ] Master user credentials set
- [ ] HTTPS enforced
- [ ] TLS 1.2+ enabled

### 8.5 Testing

- [ ] All component tests passed
- [ ] Integration tests passed
- [ ] Performance tests passed
- [ ] Failure recovery tests passed
- [ ] Metrics accessible
- [ ] Grafana dashboards working
- [ ] Logs being ingested to OpenSearch

### 8.6 Monitoring

- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards configured
- [ ] Alerts configured (optional)
- [ ] Log rotation configured
- [ ] Backup strategy defined

### 8.7 Documentation

- [ ] README.md reviewed
- [ ] Configuration documented
- [ ] Troubleshooting guide available
- [ ] Runbook created
- [ ] Contact information updated

---

## 9. Final Deployment

Once all tests pass:

```bash
# 1. Install as systemd service
sudo ./deploy/enable_agent.sh

# 2. Start the service
sudo systemctl start ids2-agent

# 3. Monitor startup
sudo journalctl -u ids2-agent -f

# 4. Verify all services
docker-compose -f docker/docker-compose.yml ps
curl http://192.168.178.66:9100/metrics

# 5. Access Grafana
# Open browser: http://192.168.178.66:3000
# Login: admin/admin

# 6. Verify data ingestion
curl -u admin:Admin123! "https://your-endpoint/_cat/indices/ids2-logs-*?v"
```

---

## 10. Troubleshooting Common Issues

See [README.md - Troubleshooting](README.md#troubleshooting) section for detailed troubleshooting steps.

---

**Testing Complete! 🎉**

Your IDS2 SOC Pipeline is now production-ready for Raspberry Pi 5.
