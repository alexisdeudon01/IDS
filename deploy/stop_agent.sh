#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Stop Agent Service
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Stop Agent Service${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Check if service is running
if ! systemctl is-active ids2-agent.service &>/dev/null; then
    echo -e "${YELLOW}Service is not running${NC}"
    exit 0
fi

# Stop service
echo -e "${YELLOW}Stopping IDS2 agent service...${NC}"
systemctl stop ids2-agent.service

# Wait for graceful shutdown
echo -e "${YELLOW}Waiting for graceful shutdown (max 30s)...${NC}"
sleep 2

# Check status
if systemctl is-active ids2-agent.service &>/dev/null; then
    echo -e "${RED}Warning: Service did not stop gracefully${NC}"
    exit 1
else
    echo -e "${GREEN}Service stopped successfully${NC}"
fi

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 Agent Stopped${NC}"
echo -e "${GREEN}============================================================================${NC}"
