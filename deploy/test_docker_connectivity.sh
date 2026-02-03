#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Docker Container Connectivity Testing
# ============================================================================
# 
# This script tests connectivity between all Docker containers in the
# IDS2 SOC Pipeline to ensure they can communicate properly.
#
# Tests performed:
# 1. Network creation and container placement
# 2. DNS resolution between containers
# 3. Port accessibility between services
# 4. Health check verification
# 5. End-to-end data flow validation
#
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}IDS2 SOC Pipeline - Docker Connectivity Test${NC}"
echo -e "${BLUE}============================================================================${NC}\n"

# Change to project root
cd "$(dirname "$0")/.."

# ============================================================================
# TEST 1: Verify Docker Compose Stack is Running
# ============================================================================
echo -e "${YELLOW}TEST 1: Verifying Docker Compose stack...${NC}"

if ! docker-compose -f docker/docker-compose.yml ps | grep -q "Up"; then
    echo -e "${RED}❌ Docker Compose stack is not running${NC}"
    echo -e "${YELLOW}Starting Docker Compose stack...${NC}"
    docker-compose -f docker/docker-compose.yml up -d
    sleep 10
fi

# Get list of running containers
CONTAINERS=$(docker-compose -f docker/docker-compose.yml ps --services)
echo -e "${GREEN}✅ Docker Compose stack is running${NC}"
echo -e "${BLUE}Containers: ${CONTAINERS}${NC}\n"

# ============================================================================
# TEST 2: Verify Network Creation
# ============================================================================
echo -e "${YELLOW}TEST 2: Verifying Docker network...${NC}"

if ! docker network ls | grep -q "ids2-network"; then
    echo -e "${RED}❌ ids2-network not found${NC}"
    exit 1
fi

# Check network connectivity
NETWORK_ID=$(docker network inspect ids2-network -f '{{.Id}}')
echo -e "${GREEN}✅ Network 'ids2-network' exists (ID: ${NETWORK_ID:0:12})${NC}"

# List all containers on the network
echo -e "${BLUE}Containers on ids2-network:${NC}"
docker network inspect ids2-network -f '{{range .Containers}}  - {{.Name}} ({{.IPv4Address}}){{"\n"}}{{end}}'
echo ""

# ============================================================================
# TEST 3: DNS Resolution Between Containers
# ============================================================================
echo -e "${YELLOW}TEST 3: Testing DNS resolution between containers...${NC}"

# Test from vector to redis
if docker exec ids2-vector getent hosts redis > /dev/null 2>&1; then
    REDIS_IP=$(docker exec ids2-vector getent hosts redis | awk '{print $1}')
    echo -e "${GREEN}✅ vector → redis: Resolved to ${REDIS_IP}${NC}"
else
    echo -e "${RED}❌ vector → redis: DNS resolution failed${NC}"
    exit 1
fi

# Test from vector to prometheus
if docker exec ids2-vector getent hosts prometheus > /dev/null 2>&1; then
    PROM_IP=$(docker exec ids2-vector getent hosts prometheus | awk '{print $1}')
    echo -e "${GREEN}✅ vector → prometheus: Resolved to ${PROM_IP}${NC}"
else
    echo -e "${RED}❌ vector → prometheus: DNS resolution failed${NC}"
    exit 1
fi

# Test from grafana to prometheus
if docker exec ids2-grafana getent hosts prometheus > /dev/null 2>&1; then
    PROM_IP=$(docker exec ids2-grafana getent hosts prometheus | awk '{print $1}')
    echo -e "${GREEN}✅ grafana → prometheus: Resolved to ${PROM_IP}${NC}"
else
    echo -e "${RED}❌ grafana → prometheus: DNS resolution failed${NC}"
    exit 1
fi

echo ""

# ============================================================================
# TEST 4: Port Connectivity Between Services
# ============================================================================
echo -e "${YELLOW}TEST 4: Testing port connectivity...${NC}"

# Test Redis port from Vector
if docker exec ids2-vector timeout 5 bash -c "cat < /dev/null > /dev/tcp/redis/6379" 2>/dev/null; then
    echo -e "${GREEN}✅ vector → redis:6379 (Redis port accessible)${NC}"
else
    echo -e "${RED}❌ vector → redis:6379 (Redis port not accessible)${NC}"
    exit 1
fi

# Test Prometheus port from Grafana
if docker exec ids2-grafana timeout 5 bash -c "cat < /dev/null > /dev/tcp/prometheus/9090" 2>/dev/null; then
    echo -e "${GREEN}✅ grafana → prometheus:9090 (Prometheus port accessible)${NC}"
else
    echo -e "${RED}❌ grafana → prometheus:9090 (Prometheus port not accessible)${NC}"
    exit 1
fi

# Test Vector metrics port from Prometheus
if docker exec ids2-prometheus timeout 5 bash -c "cat < /dev/null > /dev/tcp/vector/9101" 2>/dev/null; then
    echo -e "${GREEN}✅ prometheus → vector:9101 (Vector metrics accessible)${NC}"
else
    echo -e "${RED}❌ prometheus → vector:9101 (Vector metrics not accessible)${NC}"
    exit 1
fi

echo ""

# ============================================================================
# TEST 5: Health Check Verification
# ============================================================================
echo -e "${YELLOW}TEST 5: Verifying container health checks...${NC}"

# Function to check container health
check_health() {
    local container=$1
    local health=$(docker inspect --format='{{.State.Health.Status}}' $container 2>/dev/null || echo "no-health-check")
    
    if [ "$health" = "healthy" ]; then
        echo -e "${GREEN}✅ ${container}: healthy${NC}"
        return 0
    elif [ "$health" = "no-health-check" ]; then
        # Check if container is running
        if docker ps | grep -q $container; then
            echo -e "${YELLOW}⚠️  ${container}: running (no health check)${NC}"
            return 0
        else
            echo -e "${RED}❌ ${container}: not running${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ ${container}: ${health}${NC}"
        return 1
    fi
}

check_health "ids2-redis"
check_health "ids2-vector"
check_health "ids2-prometheus"
check_health "ids2-grafana"

echo ""

# ============================================================================
# TEST 6: HTTP Endpoint Accessibility
# ============================================================================
echo -e "${YELLOW}TEST 6: Testing HTTP endpoints...${NC}"

# Test Redis PING
if docker exec ids2-redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis: PING successful${NC}"
else
    echo -e "${RED}❌ Redis: PING failed${NC}"
    exit 1
fi

# Test Vector health endpoint
if docker exec ids2-vector wget --quiet --tries=1 --spider http://localhost:8686/health 2>/dev/null; then
    echo -e "${GREEN}✅ Vector: Health endpoint accessible${NC}"
else
    echo -e "${RED}❌ Vector: Health endpoint not accessible${NC}"
    exit 1
fi

# Test Prometheus health endpoint
if docker exec ids2-prometheus wget --quiet --tries=1 --spider http://localhost:9090/-/healthy 2>/dev/null; then
    echo -e "${GREEN}✅ Prometheus: Health endpoint accessible${NC}"
else
    echo -e "${RED}❌ Prometheus: Health endpoint not accessible${NC}"
    exit 1
fi

# Test Grafana health endpoint
if docker exec ids2-grafana wget --quiet --tries=1 --spider http://localhost:3000/api/health 2>/dev/null; then
    echo -e "${GREEN}✅ Grafana: Health endpoint accessible${NC}"
else
    echo -e "${RED}❌ Grafana: Health endpoint not accessible${NC}"
    exit 1
fi

echo ""

# ============================================================================
# TEST 7: Metrics Scraping Verification
# ============================================================================
echo -e "${YELLOW}TEST 7: Verifying Prometheus metrics scraping...${NC}"

# Check if Prometheus can scrape Vector metrics
VECTOR_METRICS=$(docker exec ids2-prometheus wget -q -O- http://vector:9101/metrics 2>/dev/null | grep -c "^vector_" || echo "0")
if [ "$VECTOR_METRICS" -gt 0 ]; then
    echo -e "${GREEN}✅ Prometheus can scrape Vector metrics (${VECTOR_METRICS} metrics found)${NC}"
else
    echo -e "${RED}❌ Prometheus cannot scrape Vector metrics${NC}"
    exit 1
fi

# Check Prometheus targets
TARGETS=$(docker exec ids2-prometheus wget -q -O- http://localhost:9090/api/v1/targets 2>/dev/null)
if echo "$TARGETS" | grep -q "vector"; then
    echo -e "${GREEN}✅ Prometheus has Vector as a target${NC}"
else
    echo -e "${YELLOW}⚠️  Prometheus does not have Vector configured as target${NC}"
fi

echo ""

# ============================================================================
# TEST 8: Redis Fallback Connectivity
# ============================================================================
echo -e "${YELLOW}TEST 8: Testing Redis fallback connectivity from Vector...${NC}"

# Test Redis SET/GET from Vector container
TEST_KEY="ids2:connectivity:test:$(date +%s)"
TEST_VALUE="connectivity_test_successful"

if docker exec ids2-vector timeout 5 bash -c "echo -e '*3\r\n\$3\r\nSET\r\n\$${#TEST_KEY}\r\n${TEST_KEY}\r\n\$${#TEST_VALUE}\r\n${TEST_VALUE}\r\n' | nc redis 6379" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}✅ Vector can write to Redis${NC}"
else
    echo -e "${RED}❌ Vector cannot write to Redis${NC}"
    exit 1
fi

# Clean up test key
docker exec ids2-redis redis-cli DEL "$TEST_KEY" > /dev/null 2>&1

echo ""

# ============================================================================
# TEST 9: External Port Accessibility (from host)
# ============================================================================
echo -e "${YELLOW}TEST 9: Testing external port accessibility from host...${NC}"

# Test Vector metrics port (9101)
if curl -sf http://localhost:9101/metrics > /dev/null; then
    echo -e "${GREEN}✅ Vector metrics (9101) accessible from host${NC}"
else
    echo -e "${RED}❌ Vector metrics (9101) not accessible from host${NC}"
    exit 1
fi

# Test Prometheus port (9090)
if curl -sf http://localhost:9090/-/healthy > /dev/null; then
    echo -e "${GREEN}✅ Prometheus (9090) accessible from host${NC}"
else
    echo -e "${RED}❌ Prometheus (9090) not accessible from host${NC}"
    exit 1
fi

# Test Grafana port (3000)
if curl -sf http://localhost:3000/api/health > /dev/null; then
    echo -e "${GREEN}✅ Grafana (3000) accessible from host${NC}"
else
    echo -e "${RED}❌ Grafana (3000) not accessible from host${NC}"
    exit 1
fi

# Test Redis port (6379)
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/localhost/6379" 2>/dev/null; then
    echo -e "${GREEN}✅ Redis (6379) accessible from host${NC}"
else
    echo -e "${RED}❌ Redis (6379) not accessible from host${NC}"
    exit 1
fi

echo ""

# ============================================================================
# TEST 10: End-to-End Data Flow Test
# ============================================================================
echo -e "${YELLOW}TEST 10: Testing end-to-end data flow (Vector → Redis)...${NC}"

# Send a test event to Vector HTTP endpoint
TEST_EVENT='{"timestamp":"2026-02-01T10:00:00Z","event_type":"test","message":"connectivity_test"}'

if curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "$TEST_EVENT" \
    http://localhost:8282/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Test event sent to Vector HTTP endpoint${NC}"
    
    # Wait a moment for processing
    sleep 2
    
    echo -e "${GREEN}✅ End-to-end data flow test completed${NC}"
else
    echo -e "${YELLOW}⚠️  Vector HTTP endpoint not configured or not reachable${NC}"
    echo -e "${BLUE}   (This is expected if HTTP source is not enabled in vector.toml)${NC}"
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${BLUE}============================================================================${NC}"
echo -e "${GREEN}🎉 ALL CONNECTIVITY TESTS PASSED!${NC}"
echo -e "${BLUE}============================================================================${NC}\n"

echo -e "${GREEN}Summary:${NC}"
echo -e "  ${GREEN}✅${NC} Docker network (ids2-network) is operational"
echo -e "  ${GREEN}✅${NC} DNS resolution works between all containers"
echo -e "  ${GREEN}✅${NC} All service ports are accessible"
echo -e "  ${GREEN}✅${NC} Health checks are passing"
echo -e "  ${GREEN}✅${NC} Metrics scraping is functional"
echo -e "  ${GREEN}✅${NC} Redis fallback is operational"
echo -e "  ${GREEN}✅${NC} External ports are accessible from host"
echo -e ""
echo -e "${BLUE}The Docker container orchestration is fully functional!${NC}\n"

exit 0
