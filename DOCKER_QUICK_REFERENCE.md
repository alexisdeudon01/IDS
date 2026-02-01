# IDS2 SOC Pipeline - Docker Quick Reference

## Quick Commands

### Start/Stop Stack
```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Stop all services
docker-compose -f docker/docker-compose.yml down

# Restart specific service
docker-compose -f docker/docker-compose.yml restart vector

# Stop without removing volumes
docker-compose -f docker/docker-compose.yml stop
```

### View Status
```bash
# List all containers
docker-compose -f docker/docker-compose.yml ps

# View resource usage
docker stats

# Check health status
docker-compose -f docker/docker-compose.yml ps --format json | jq -r '.[] | "\(.Service): \(.State)"'
```

### Logs
```bash
# Follow all logs
docker-compose -f docker/docker-compose.yml logs -f

# Follow specific service
docker-compose -f docker/docker-compose.yml logs -f vector

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100 vector

# Logs since timestamp
docker-compose -f docker/docker-compose.yml logs --since 2026-02-01T10:00:00 vector
```

### Execute Commands in Containers
```bash
# Open shell in Vector container
docker exec -it ids2-vector /bin/bash

# Run command in Redis
docker exec ids2-redis redis-cli ping

# Check Vector config
docker exec ids2-vector cat /etc/vector/vector.toml
```

### Networking
```bash
# Inspect network
docker network inspect ids2-network

# Test DNS from Vector to Redis
docker exec ids2-vector getent hosts redis

# Test port connectivity
docker exec ids2-vector timeout 5 bash -c "cat < /dev/null > /dev/tcp/redis/6379"
```

### Build & Update
```bash
# Rebuild agent image
docker build -t ids2-agent:latest -f Dockerfile .

# Pull latest service images
docker-compose -f docker/docker-compose.yml pull

# Rebuild specific service
docker-compose -f docker/docker-compose.yml build vector

# Update and restart
docker-compose -f docker/docker-compose.yml up -d --build
```

### Cleanup
```bash
# Remove stopped containers
docker-compose -f docker/docker-compose.yml rm

# Remove all (including volumes)
docker-compose -f docker/docker-compose.yml down -v

# Clean Docker system
docker system prune -a

# Remove specific volume
docker volume rm ids2_vector-data
```

## Service-Specific Commands

### Vector
```bash
# Check health
curl http://localhost:8686/health

# View metrics
curl http://localhost:9101/metrics

# Send test event
curl -X POST -H "Content-Type: application/json" \
  -d '{"test":"event"}' http://localhost:8282/

# Validate config (in container)
docker exec ids2-vector vector validate /etc/vector/vector.toml
```

### Redis
```bash
# Ping
docker exec ids2-redis redis-cli ping

# Get info
docker exec ids2-redis redis-cli info

# Monitor commands
docker exec ids2-redis redis-cli monitor

# Check keys
docker exec ids2-redis redis-cli keys '*'

# Get memory usage
docker exec ids2-redis redis-cli info memory
```

### Prometheus
```bash
# Check health
curl http://localhost:9090/-/healthy

# Check targets
curl http://localhost:9090/api/v1/targets | jq

# Query metric
curl 'http://localhost:9090/api/v1/query?query=up' | jq

# Check config
curl http://localhost:9090/api/v1/status/config | jq
```

### Grafana
```bash
# Check health
curl http://localhost:3000/api/health

# List dashboards
curl -u admin:admin http://localhost:3000/api/search

# Test datasource
curl -u admin:admin http://localhost:3000/api/datasources/1/health
```

## Troubleshooting Commands

### Container Won't Start
```bash
# Check logs
docker logs ids2-vector

# Check last exit code
docker inspect ids2-vector --format='{{.State.ExitCode}}'

# Check restart count
docker inspect ids2-vector --format='{{.RestartCount}}'

# Force remove and recreate
docker-compose -f docker/docker-compose.yml rm -f vector
docker-compose -f docker/docker-compose.yml up -d vector
```

### High Resource Usage
```bash
# Check container stats
docker stats ids2-vector

# Check throttle level
curl http://localhost:9100/metrics | grep throttle

# Limit CPU (temporary)
docker update --cpus="0.5" ids2-vector

# Check memory usage
docker exec ids2-vector free -h
```

### Network Issues
```bash
# Run connectivity test
./deploy/test_docker_connectivity.sh

# Visualize network topology
python3 deploy/visualize_network.py

# Recreate network
docker-compose -f docker/docker-compose.yml down
docker network rm ids2-network
docker-compose -f docker/docker-compose.yml up -d
```

### Configuration Issues
```bash
# Verify Vector config
docker exec ids2-vector vector validate /etc/vector/vector.toml

# Check environment variables
docker exec ids2-vector env | grep AWS

# Check mounted volumes
docker inspect ids2-vector --format='{{range .Mounts}}{{.Source}}:{{.Destination}}{{"\n"}}{{end}}'

# Reload configuration (if supported)
docker-compose -f docker/docker-compose.yml restart vector
```

## Monitoring Commands

### Real-time Monitoring
```bash
# Watch all container stats
watch -n 2 'docker stats --no-stream'

# Watch Vector metrics
watch -n 2 'curl -s http://localhost:9101/metrics | grep vector_component'

# Watch agent metrics
watch -n 2 'curl -s http://localhost:9100/metrics | grep ids2_'

# Watch Redis info
watch -n 2 'docker exec ids2-redis redis-cli info stats'
```

### Performance Analysis
```bash
# Vector throughput
curl -s http://localhost:9101/metrics | grep vector_component_sent_events_total

# Redis memory
docker exec ids2-redis redis-cli info memory | grep used_memory_human

# Prometheus storage
curl -s http://localhost:9090/api/v1/status/tsdb | jq

# Container resource limits
docker inspect ids2-vector --format='CPU: {{.HostConfig.CpuQuota}}, RAM: {{.HostConfig.Memory}}'
```

## Backup & Restore

### Backup Volumes
```bash
# Backup Vector data
docker run --rm -v ids2_vector-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/vector-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup Redis data
docker run --rm -v ids2_redis-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/redis-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup Prometheus data
docker run --rm -v ids2_prometheus-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup Grafana data
docker run --rm -v ids2_grafana-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana-data-$(date +%Y%m%d).tar.gz -C /data .
```

### Restore Volumes
```bash
# Restore Vector data
docker run --rm -v ids2_vector-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/vector-data-20260201.tar.gz -C /data

# Restore Redis data
docker run --rm -v ids2_redis-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/redis-data-20260201.tar.gz -C /data
```

## Configuration Files

### Key Paths
```
docker/docker-compose.yml       # Service orchestration
docker/prometheus.yml           # Prometheus scrape config
docker/grafana/provisioning/    # Grafana auto-config
vector/vector.toml              # Vector config (generated)
config.yaml                     # Main configuration
.env                           # Environment variables
```

### Edit and Reload
```bash
# 1. Edit configuration
nano docker/docker-compose.yml

# 2. Validate
docker-compose -f docker/docker-compose.yml config

# 3. Apply changes
docker-compose -f docker/docker-compose.yml up -d

# 4. Verify
docker-compose -f docker/docker-compose.yml ps
```

## Useful Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Docker Compose shortcuts
alias dcp='docker-compose -f docker/docker-compose.yml'
alias dcup='docker-compose -f docker/docker-compose.yml up -d'
alias dcdown='docker-compose -f docker/docker-compose.yml down'
alias dcps='docker-compose -f docker/docker-compose.yml ps'
alias dclogs='docker-compose -f docker/docker-compose.yml logs -f'

# Container shortcuts
alias dvector='docker exec -it ids2-vector'
alias dredis='docker exec -it ids2-redis redis-cli'
alias dprom='docker exec -it ids2-prometheus'
alias dgrafana='docker exec -it ids2-grafana'

# Monitoring shortcuts
alias watchdocker='watch -n 2 docker stats --no-stream'
alias ids2metrics='curl -s http://localhost:9100/metrics | grep ids2_'
alias vectormetrics='curl -s http://localhost:9101/metrics | grep vector_'
```

## Emergency Procedures

### Complete Stack Restart
```bash
# 1. Stop everything
docker-compose -f docker/docker-compose.yml down

# 2. Clean up
docker system prune -f

# 3. Verify clean state
docker ps -a
docker network ls

# 4. Restart stack
docker-compose -f docker/docker-compose.yml up -d

# 5. Wait for health
sleep 30

# 6. Test connectivity
./deploy/test_docker_connectivity.sh
```

### Reset to Clean State
```bash
# WARNING: This removes ALL data!

# 1. Stop and remove everything
docker-compose -f docker/docker-compose.yml down -v

# 2. Remove network
docker network rm ids2-network || true

# 3. Clean Docker
docker system prune -a -f --volumes

# 4. Rebuild from scratch
docker build -t ids2-agent:latest -f Dockerfile .
docker-compose -f docker/docker-compose.yml up -d

# 5. Verify
./deploy/test_docker_connectivity.sh
```

## Tips & Best Practices

1. **Always use docker-compose** - Don't start containers manually
2. **Check logs first** - Most issues show up in logs
3. **Test connectivity** - Run `test_docker_connectivity.sh` after changes
4. **Monitor resources** - Use `docker stats` to watch CPU/RAM
5. **Backup volumes** - Before major changes, backup data
6. **Use health checks** - Wait for containers to be healthy
7. **Check DNS** - Most network issues are DNS-related
8. **Version control** - Commit docker-compose.yml changes
9. **Document changes** - Add comments to configurations
10. **Test in isolation** - Start one service at a time when troubleshooting
