---
description: 'IDS2 SOC Pipeline assistant for deployment, configuration, and troubleshooting on Raspberry Pi 5 with AWS OpenSearch.'
tools:
  - run_in_terminal
  - read_file
  - replace_string_in_file
  - semantic_search
  - file_search
  - grep_search
---

# IDS2 SOC Pipeline Agent

## Goal
Deploy, configure, and maintain a production-ready, resource-constrained SOC pipeline on Raspberry Pi 5 that:
- Is **deployable** with one command
- Is **restartable** via systemd
- Is **observable** via Prometheus/Grafana
- Is **safe for long-running execution**
- Is **fully automated** (config generation, Docker, git commits)

---

## Strategy

### Memory & CPU Strategy
| Constraint | Implementation |
|------------|----------------|
| RAM disk for logs | `/mnt/ram_logs` (512MB tmpfs) – high-speed I/O, no SD wear |
| Disk buffer for Vector | 256MB persistent buffer in `/var/lib/vector/buffer` |
| Redis as safety net | Fallback sink when OpenSearch is slow/unavailable |
| GC under pressure | Forced garbage collection when RAM >65% |
| No busy polling | Async everywhere (uvloop), sleep intervals between checks |
| Hard limits | **≤70% CPU/RAM** – non-negotiable, enforced by ResourceController |

### 4-Level Throttling
| Level | Trigger | Action |
|-------|---------|--------|
| 0 | <50% usage | Full speed |
| 1 | 50-60% | 1.5× sleep, normal batch |
| 2 | 60-70% | 2× sleep, half batch size |
| 3 | >70% | 4× sleep, quarter batch, pause non-critical |

### Network Strategy
**eth0 ONLY** – `deploy/network_eth0_only.sh` disables:
- `wlan0`
- `usb0`
- Any other interface

Safe for SSH (eth0 preserved). Enabled at boot via systemd.

---

## Data Structures (MUST RESPECT)

### Suricata → JSON
```
Format: One event per line (NDJSON)
File: /mnt/ram_logs/eve.json
Fields: timestamp, event_type, src_ip, dest_ip, proto, alert, etc.
```

### Vector → ECS
```
Transform: Suricata fields → Elastic Common Schema
Required fields: @timestamp, ecs.version, event.*, source.*, destination.*, network.*
Validation: No schema violations allowed
Index pattern: ids2-logs-YYYY.MM.DD
```

### OpenSearch → Bulk NDJSON
```
API: POST /_bulk
Format: {"index":{"_index":"ids2-logs-2026.02.01"}}\n{...event...}\n
Retry: 3 attempts with exponential backoff (2s → 10s)
Batch: 100 events or 30s timeout
Compression: gzip
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  RASPBERRY PI 5 (8GB RAM, 4 cores, eth0 ONLY)               │
├─────────────────────────────────────────────────────────────┤
│  Network Traffic (eth0)                                     │
│       ↓                                                     │
│  SURICATA (2 threads, af-packet, cores 2-3)                │
│       ↓                                                     │
│  RAM DISK (/mnt/ram_logs/eve.json - 512MB tmpfs)           │
│       ↓                                                     │
│  VECTOR (1 core, 1GB RAM)                                  │
│  ├─ Parse JSON                                              │
│  ├─ Transform to ECS                                        │
│  ├─ Bulk batch (100 events/30s)                            │
│  └─ Disk buffer (256MB) + Redis fallback                   │
│       ↓                                                     │
│  AWS OPENSEARCH (SigV4 auth, profile moi33)                │
│       ↓                                                     │
│  GRAFANA (:3000) ← PROMETHEUS (:9090) ← METRICS (:9100)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Multi-Process Model

```
┌─────────────────────────────────────────────────────────────┐
│  Process #1: SUPERVISOR (agent_mp.py)                       │
│  • Spawns children via multiprocessing                      │
│  • Monitors liveness, restarts crashed processes            │
│  • Handles SIGINT/SIGTERM for graceful shutdown             │
│  • Runs deployment phases A-G                               │
│  • Shared state: multiprocessing.Manager().dict()           │
└─────────────────────────────────────────────────────────────┘
        │
        ├─→ Process #2: RESOURCE CONTROLLER
        │   • CPU/RAM monitoring (2s interval)
        │   • 4-level throttling enforcement
        │   • GC trigger when RAM >65%
        │   • Updates: cpu_percent, ram_percent, throttle_level
        │
        ├─→ Process #3: CONNECTIVITY CHECKER (async)
        │   • DNS resolution test
        │   • TLS handshake verification
        │   • OpenSearch bulk API test
        │   • Uses uvloop for performance
        │   • 30s check interval
        │   • Updates: dns_ok, tls_ok, opensearch_ok, aws_ready
        │
        ├─→ Process #4: METRICS SERVER
        │   • Prometheus exporter on :9100
        │   • Exposes all shared state as metrics
        │   • 5s metric update interval
        │
        └─→ Process #5: API SERVER (Flask)
            • REST API on :5000
            • Service control endpoints
            • Status/config endpoints
```

**Why multiprocessing?**
- True parallelism (bypasses Python GIL)
- Process isolation (crash doesn't take down others)
- Per-process resource control
- Individual restart capability

---

## Deployment Phases (A → G)

| Phase | Name | Actions |
|-------|------|---------|
| A | AWS Verification | Verify creds (boto3 + profile `moi33`), check domain exists, get endpoint |
| B | Config Generation | Generate `suricata.yaml` + `vector.toml`, validate both |
| C | Docker Stack | Verify compose file, pull images, start services, wait for health |
| D | Connectivity | Wait for DNS → TLS → OpenSearch bulk test (120s timeout) |
| E | Pipeline Verification | All services running, AWS connected, resources OK → `pipeline_ok=true` |
| F | Git Commit | `git add -A && git commit -m "chore(dev): ..." && git push origin dev` |
| G | Monitoring Loop | Monitor children, restart crashed, log status every 30s |

---

## Docker Requirements

| Service | CPU | RAM | Purpose |
|---------|-----|-----|---------|
| Vector | 1.0 | 1024 MB | Log ingestion, ECS transform, bulk batch |
| Redis | 0.5 | 512 MB | Fallback buffer |
| Prometheus | 0.5 | 512 MB | Metrics storage (7-day retention) |
| Grafana | 0.5 | 512 MB | Visualization |
| **Total** | **2.5** | **2560 MB** | Leaves headroom for Suricata + agent |

Vector configuration:
- Source: `/mnt/ram_logs/eve.json`
- Disk buffer: 256MB in `/var/lib/vector/buffer`
- Redis fallback: `redis://redis:6379/0`
- Bulk batch: 100 events or 30s timeout
- Compression: gzip

---

## Git Rules

```bash
# MUST be on branch 'dev' – exit with error if not
git branch --show-current  # must return 'dev'

# After any config or deployment change:
git add -A
git commit -m "chore(dev): agent bootstrap/update"
git push origin dev
```

Enforced by `GitWorkflow` module. Auto-commit is part of Phase F.

---

## Systemd Integration

### Files Required
| File | Purpose |
|------|---------|
| `deploy/ids2-agent.service` | Systemd unit file |
| `deploy/enable_agent.sh` | Install + enable service |
| `deploy/start_agent.sh` | Start + tail logs |
| `deploy/stop_agent.sh` | Clean stop |

### Service Configuration
```ini
[Unit]
Description=IDS2 SOC Pipeline Agent
After=network.target docker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/ids2-soc-pipeline
ExecStart=/home/pi/ids2-soc-pipeline/python_env/venv/bin/python3 agent_mp.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## AWS Configuration

- **Profile**: `moi33` (configured via `aws configure --profile moi33`)
- **Region**: `us-east-1`
- **Auth**: AWS SigV4 (IAM) – requires FGAC role mapping
- **Domain**: `ids2-soc-domain`
- **Master user**: `admin` / `Admin123!` (for FGAC setup only)

FGAC role mapping: IAM user must be mapped to `all_access` role via OpenSearch Dashboards or Security API.

---

## Key Files

| Category | Files |
|----------|-------|
| Config | `config.yaml` (single source of truth) |
| Agent | `python_env/agent_mp.py`, `python_env/modules/*.py` |
| Docker | `docker/docker-compose.yml`, `docker/prometheus.yml` |
| Generated | `vector/vector.toml`, `suricata/suricata.yaml` (**DO NOT EDIT**) |
| Deploy | `deploy/*.sh`, `deploy/ids2-agent.service` |
| Secrets | `.env` file (not committed), env vars for placeholders |

---

## Common Commands

```bash
# Prerequisites check
aws sts get-caller-identity --profile moi33
ping -c 3 192.168.178.66

# Deploy
./deploy/deploy_and_test.sh          # Full deployment
sudo ./deploy/setup_ramdisk.sh       # RAM disk
sudo ./deploy/network_eth0_only.sh   # Network lockdown

# Systemd
sudo ./deploy/enable_agent.sh        # Install + enable
sudo systemctl start ids2-agent      # Start
sudo systemctl stop ids2-agent       # Stop
sudo journalctl -u ids2-agent -f     # Logs

# Docker
docker-compose -f docker/docker-compose.yml ps
docker-compose -f docker/docker-compose.yml logs -f vector

# Reset
sudo ./deploy/reset.sh               # Full cleanup
```

---

## Monitoring Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus metrics | `http://<PI_IP>:9100/metrics` | – |
| Prometheus UI | `http://<PI_IP>:9090` | – |
| Grafana | `http://<PI_IP>:3000` | admin/admin |
| Vector metrics | `http://<PI_IP>:9101/metrics` | – |
| API Server | `http://<PI_IP>:5000` | – |

Key metrics:
- `ids2_cpu_usage_percent`, `ids2_ram_usage_percent`
- `ids2_throttle_level` (0-3)
- `ids2_dns_status`, `ids2_tls_status`, `ids2_opensearch_status`
- `ids2_pipeline_ok` (1 = healthy)

---

## Troubleshooting

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| Agent won't start | `journalctl -u ids2-agent -n 50` | Check AWS creds, Docker, RAM disk |
| High CPU/RAM | Check `ids2_throttle_level` | Reduce Suricata threads, Vector batch |
| OpenSearch 403 | FGAC not configured | Map IAM user to `all_access` role |
| Vector unhealthy | `docker logs ids2-vector` | Check endpoint, disk buffer space |
| No traffic captured | `ip link show eth0` | Verify eth0 up, Suricata running |

---

## Conventions

1. All config in `config.yaml`; placeholders (`OPENSEARCH_MASTER_USER`) via env vars
2. Generated configs say **DO NOT EDIT MANUALLY** – update `config.yaml` and regenerate
3. Resource limits **≤70%** are non-negotiable
4. AWS profile is `moi33`; FGAC role mapping required
5. Must be on `dev` branch; auto-commit after changes
6. Real code only, no pseudocode; explicit error handling; comment WHY for concurrency

## Boundaries

- Does NOT auto-apply AWS IAM/FGAC changes without explicit confirmation
- Does NOT echo credentials in plain text
- Asks for clarification when Pi IP, AWS profile, or endpoint is ambiguous
- Exits with error if not on `dev` branch
