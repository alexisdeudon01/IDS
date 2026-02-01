# IDS2 SOC Pipeline - Docker Deployment

This directory contains the Docker Compose stack for the IDS2 SOC Pipeline, including the containerized Python agent.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐ │
│  │  IDS2 Agent  │  │  Vector  │  │ Prometheus │  │ Grafana  │ │
│  │  (Python)    │  │          │  │            │  │          │ │
│  │  Port: 9100  │  │ Port:    │  │ Port: 9090 │  │Port: 3000│ │
│  │              │  │ 9101,8686│  │            │  │          │ │
│  └──────┬───────┘  └────┬─────┘  └─────┬──────┘  └────┬─────┘ │
│         │               │              │              │        │
│         └───────────────┴──────────────┴──────────────┘        │
│                         │                                       │
│                    ┌────┴─────┐                                │
│                    │  Redis   │                                │
│                    │Port: 6379│                                │
│                    └──────────┘                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Services

### 1. IDS2 Agent (Containerized Python Agent)
- **Image**: `ids2-agent:latest` (built from Dockerfile)
- **Purpose**: Multi-process orchestrator for the entire pipeline
- **Ports**: 9100 (Prometheus metrics)
- **Resources**: 1.5 CPU, 2GB RAM
- **Volumes**:
  - Config file (read-only)
  - AWS credentials (read-only)
  - Git repository (read-write for auto-commit)
  - Docker socket (for container management)
  - RAM logs (shared with Suricata)

### 2. Vector
- **Image**: `timberio/vector:0.34.0-debian`
- **Purpose**: Log ingestion and transformation
- **Ports**: 9101 (metrics), 8686 (health)
- **Resources**: 1 CPU, 1GB RAM

### 3. Redis
- **Image**: `redis:7-alpine`
- **Purpose**: Fallback buffer for logs
- **Port**: 6379
- **Resources**: 0.5 CPU, 512MB RAM

### 4. Prometheus
- **Image**: `prom/prometheus:v2.48.0`
- **Purpose**: Metrics storage and querying
- **Port**: 9090
- **Resources**: 0.5 CPU, 512MB RAM
- **Retention**: 7 days, 2GB max

### 5. Grafana
- **Image**: `grafana/grafana:10.2.2`
- **Purpose**: Metrics visualization
- **Port**: 3000
- **Resources**: 0.5 CPU, 512MB RAM
- **Credentials**: admin/admin

## 🚀 Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB RAM (Raspberry Pi 5)
- AWS credentials configured (`~/.aws/credentials` with profile `moi33`)

### 1. Build the IDS2 Agent Image
```bash
cd docker
./build.sh
```

### 2. Start the Stack
```bash
docker-compose up -d
```

### 3. Check Status
```bash
docker-compose ps
```

### 4. View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ids2-agent
docker-compose logs -f vector
```

### 5. Access Services
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **IDS2 Metrics**: http://localhost:9100/metrics

## 🔧 Management Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose stop
```

### Restart a Service
```bash
docker-compose restart ids2-agent
```

### View Resource Usage
```bash
docker stats
```

### Remove Everything (including volumes)
```bash
docker-compose down -v
```

### Rebuild Agent Image
```bash
docker-compose build ids2-agent
docker-compose up -d ids2-agent
```

## 📊 Monitoring

### Health Checks
All services have health checks configured:
```bash
docker-compose ps
```

Look for `(healthy)` status.

### Metrics Endpoints
- IDS2 Agent: http://localhost:9100/metrics
- Vector: http://localhost:9101/metrics
- Prometheus: http://localhost:9090/metrics

### Grafana Dashboard
1. Open http://localhost:3000
2. Login with admin/admin
3. Navigate to "IDS2 SOC Pipeline - Overview" dashboard

## 🐛 Troubleshooting

### Agent Not Starting
```bash
# Check logs
docker-compose logs ids2-agent

# Check if config file exists
ls -la ../config.yaml

# Check AWS credentials
ls -la ~/.aws/credentials
```

### Vector Not Connecting to OpenSearch
```bash
# Check Vector logs
docker-compose logs vector

# Verify OpenSearch endpoint in config
cat ../config.yaml | grep opensearch
```

### High Memory Usage
```bash
# Check resource usage
docker stats

# Adjust limits in docker-compose.yml if needed
```

### Permission Issues
```bash
# Fix Docker socket permissions
sudo chmod 666 /var/run/docker.sock

# Fix AWS credentials permissions
chmod 600 ~/.aws/credentials
```

## 📁 Volume Persistence

Data is persisted in Docker volumes:
- `agent-logs`: IDS2 agent logs
- `vector-data`: Vector disk buffer
- `redis-data`: Redis persistence
- `prometheus-data`: Prometheus TSDB
- `grafana-data`: Grafana dashboards and settings

### Backup Volumes
```bash
# Backup Prometheus data
docker run --rm -v ids2_prometheus-data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data

# Backup Grafana data
docker run --rm -v ids2_grafana-data:/data -v $(pwd):/backup alpine tar czf /backup/grafana-backup.tar.gz /data
```

## 🔐 Security Notes

1. **Docker Socket**: The agent container has access to the Docker socket for container management. This is required but should be monitored.

2. **AWS Credentials**: Mounted read-only from `~/.aws`. Ensure proper file permissions (600).

3. **Git Repository**: Mounted read-write for auto-commit functionality. The agent will commit configuration changes.

4. **Network**: All services are on an isolated bridge network (`ids2-network`).

## 🎯 Resource Allocation

Total resources allocated (Raspberry Pi 5 optimized):
- **CPU**: ~4.5 cores max (out of 4 available)
- **RAM**: ~4.5GB max (out of 8GB available)

This leaves headroom for:
- Suricata (running on host)
- System processes
- Burst capacity

## 📝 Configuration

### Environment Variables
Edit `docker-compose.yml` to modify:
- `AWS_PROFILE`: AWS credentials profile name
- `PYTHONUNBUFFERED`: Python output buffering
- Grafana admin credentials

### Resource Limits
Adjust in `docker-compose.yml` under each service's `deploy.resources` section.

### Network Configuration
The stack uses subnet `172.28.0.0/16`. Modify in `docker-compose.yml` if conflicts occur.

## 🔄 Updates

### Update Agent Code
```bash
# Rebuild image
docker-compose build ids2-agent

# Restart with new image
docker-compose up -d ids2-agent
```

### Update Other Services
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose up -d
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Vector Documentation](https://vector.dev/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
