#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Complete Reset
# Stops all services, removes containers, clears logs
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}============================================================================${NC}"
echo -e "${RED}IDS2 SOC Pipeline - COMPLETE RESET${NC}"
echo -e "${RED}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will:${NC}"
echo -e "${YELLOW}  - Stop the IDS2 agent service${NC}"
echo -e "${YELLOW}  - Stop and remove all Docker containers${NC}"
echo -e "${YELLOW}  - Remove Docker volumes (data will be lost!)${NC}"
echo -e "${YELLOW}  - Clear RAM disk logs${NC}"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

# Get the actual user
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)
PROJECT_DIR="$ACTUAL_HOME/ids2-soc-pipeline"

echo ""
echo -e "${YELLOW}Step 1: Stopping IDS2 agent service...${NC}"
if systemctl is-active ids2-agent.service &>/dev/null; then
    systemctl stop ids2-agent.service
    echo -e "${GREEN}✓ Agent stopped${NC}"
else
    echo -e "${YELLOW}Agent not running${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Stopping Docker containers...${NC}"
if [ -f "$PROJECT_DIR/docker/docker-compose.yml" ]; then
    cd "$PROJECT_DIR"
    docker-compose -f docker/docker-compose.yml down --volumes --remove-orphans
    echo -e "${GREEN}✓ Docker containers stopped and removed${NC}"
else
    echo -e "${YELLOW}Docker Compose file not found${NC}"
fi

echo ""
echo -e "${YELLOW}Step 3: Removing Docker volumes...${NC}"
docker volume ls -q | grep -E 'ids2|vector|redis|prometheus|grafana' | xargs -r docker volume rm || true
echo -e "${GREEN}✓ Docker volumes removed${NC}"

echo ""
echo -e "${YELLOW}Step 4: Clearing RAM disk logs...${NC}"
if [ -d "/mnt/ram_logs" ]; then
    rm -f /mnt/ram_logs/*.json
    echo -e "${GREEN}✓ RAM disk logs cleared${NC}"
else
    echo -e "${YELLOW}RAM disk not mounted${NC}"
fi

echo ""
echo -e "${YELLOW}Step 5: Clearing system logs...${NC}"
if [ -d "/var/log/ids2" ]; then
    rm -f /var/log/ids2/*.log
    echo -e "${GREEN}✓ System logs cleared${NC}"
else
    echo -e "${YELLOW}Log directory not found${NC}"
fi

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Reset Complete${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}To start fresh:${NC}"
echo -e "  1. Setup RAM disk: sudo ./deploy/setup_ramdisk.sh"
echo -e "  2. Start agent: sudo systemctl start ids2-agent"
echo ""
