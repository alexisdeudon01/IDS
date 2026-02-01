# IDS2 SOC Pipeline - Quick Start Guide

## 🚀 One-Command Deployment

This guide will help you deploy the complete IDS2 SOC Pipeline in minutes.

---

## Prerequisites

✅ Raspberry Pi 5 (8GB RAM) at **192.168.178.66**  
✅ AWS account with credentials configured (profile: **moi33**)  
✅ SSH access to Raspberry Pi (user: **pi**, password: **pi**)  
✅ Python 3.11+ and boto3 installed locally  

---

## Step 1: Run Master Deployment Script

From your local machine:

```bash
cd /tmp/blackbox-worktrees/r
./deploy/deploy_and_test.sh
```

This script will:
1. ✅ Create AWS OpenSearch domain (15 minutes)
2. ✅ Deploy files to Raspberry Pi
3. ✅ Run comprehensive tests (15 tests)

**Total Time: ~20-25 minutes**

---

## Step 2: Manual Steps on Raspberry Pi

SSH to Raspberry Pi:

```bash
ssh pi@192.168.178.66
cd ids2-soc-pipeline
```

### 2.1 Setup RAM Disk

```bash
sudo ./deploy/setup_ramdisk.sh
```

### 2.2 Install Python Dependencies

```bash
cd python_env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.3 Install as Systemd Service

```bash
sudo ./deploy/enable_agent.sh
```

### 2.4 Start the Agent

```bash
sudo systemctl start ids2-agent
```

### 2.5 Monitor Logs

```bash
sudo journalctl -u ids2-agent -f
```

---

## Step 3: Access Monitoring

### Grafana Dashboard
- URL: http://192.168.178.66:3000
- Username: `admin`
- Password: `admin` (change on first login)

### Prometheus
- URL: http://192.168.178.66:9090

### Metrics Endpoint
- URL: http://192.168.178.66:9100/metrics

---

## Alternative: Manual Step-by-Step

If you prefer manual deployment:

### 1. Create OpenSearch Domain

```bash
python3 deploy/create_opensearch_domain.py
```

### 2. Copy Files to Pi

```bash
rsync -avz --exclude='.git' ./ pi@192.168.178.66:/home/pi/ids2-soc-pipeline/
```

### 3. Run Tests

```bash
python3 deploy/run_all_tests.py
```

### 4. Follow Step 2 above

---

## Verification

Check that everything is running:

```bash
# On Raspberry Pi
docker-compose -f docker/docker-compose.yml ps
sudo systemctl status ids2-agent
curl http://localhost:9100/metrics | grep ids2_
```

Expected output:
- All Docker services: **Up (healthy)**
- Agent service: **active (running)**
- Metrics: Multiple `ids2_*` metrics visible

---

## Troubleshooting

### OpenSearch Domain Creation Fails

```bash
# Check AWS credentials
aws sts get-caller-identity --profile moi33

# Check if domain already exists
aws opensearch describe-domain --domain-name ids2-soc-domain --profile moi33
```

### Cannot SSH to Raspberry Pi

```bash
# Test connection
ping 192.168.178.66

# Try with password
ssh -o PreferredAuthentications=password pi@192.168.178.66
```

### Tests Fail

```bash
# Check individual components
python3 deploy/run_all_tests.py

# Review logs
ssh pi@192.168.178.66 "tail -100 /var/log/syslog"
```

### Docker Services Won't Start

```bash
# On Raspberry Pi
docker-compose -f docker/docker-compose.yml logs
docker system prune -a  # Clean up
docker-compose -f docker/docker-compose.yml up -d
```

---

## Configuration Variables

All configuration is centralized in these files:

### `deploy/create_opensearch_domain.py`
```python
CONFIG = {
    'aws_profile': 'moi33',
    'aws_region': 'us-east-1',
    'domain_name': 'ids2-soc-domain',
    'instance_type': 't3.small.search',
    'master_username': 'admin',
    'master_password': 'Admin123!',  # CHANGE THIS!
    'allowed_ip': '192.168.178.66/32',
}
```

### `deploy/run_all_tests.py`
```python
CONFIG = {
    'pi_host': '192.168.178.66',
    'pi_user': 'pi',
    'pi_password': 'pi',
    'project_dir': '/home/pi/ids2-soc-pipeline',
}
```

### `config.yaml`
```yaml
raspberry_pi:
  ip_address: "192.168.178.66"
  hostname: "192.168.178.66"

aws:
  profile: "moi33"
  region: "us-east-1"
  opensearch_domain: "ids2-soc-domain"
```

---

## What Gets Created

### AWS Resources
- 1x OpenSearch domain (t3.small.search, 10GB)
- PUBLIC access with IP restriction (192.168.178.66/32)
- Cost: ~$30-40/month

### Raspberry Pi Services
- Docker containers: Vector, Redis, Prometheus, Grafana
- Systemd service: ids2-agent
- RAM disk: /mnt/ram_logs (512MB)
- Python virtual environment

### Files Created (31 total)
- 13 Python modules (~4,000 lines)
- 6 configuration files
- 2 auto-generated configs (Vector, Suricata)
- 10 deployment scripts
- 4 documentation files

---

## Success Criteria

✅ OpenSearch domain active  
✅ All 15 tests passed  
✅ Docker services running  
✅ Agent service active  
✅ Metrics being collected  
✅ Grafana accessible  
✅ Data flowing to OpenSearch  

---

## Next Steps After Deployment

1. **Configure Suricata Rules**
   - Update `/etc/suricata/rules/suricata.rules`
   - Restart agent: `sudo systemctl restart ids2-agent`

2. **Customize Grafana Dashboards**
   - Login to Grafana
   - Modify pre-configured dashboard
   - Add custom panels

3. **Setup Alerts** (Optional)
   - Configure Prometheus alerting rules
   - Setup Alertmanager
   - Integrate with notification channels

4. **Monitor Performance**
   - Watch resource usage in Grafana
   - Adjust throttling thresholds if needed
   - Tune Suricata workers

5. **Backup Configuration**
   - Backup config.yaml
   - Backup Grafana dashboards
   - Document custom changes

---

## Support

- **Documentation**: See README.md, TESTING_GUIDE.md
- **Logs**: `sudo journalctl -u ids2-agent -f`
- **Metrics**: http://192.168.178.66:9100/metrics
- **Status**: `sudo systemctl status ids2-agent`

---

**Ready to deploy? Run: `./deploy/deploy_and_test.sh`**
