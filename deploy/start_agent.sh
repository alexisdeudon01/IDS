#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Start Agent Service
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Start Agent Service${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Check if service is enabled
if ! systemctl is-enabled ids2-agent.service &>/dev/null; then
    echo -e "${YELLOW}Warning: Service is not enabled${NC}"
    echo -e "${YELLOW}Run 'sudo ./enable_agent.sh' first${NC}"
    exit 1
fi

# Start service
echo -e "${YELLOW}Starting IDS2 agent service...${NC}"
systemctl start ids2-agent.service

# Wait a moment for startup
sleep 2

# Check status
echo -e "${YELLOW}Checking service status...${NC}"
systemctl status ids2-agent.service --no-pager

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Service started!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Monitoring logs (Ctrl+C to exit):${NC}"
echo ""

# Tail logs
journalctl -u ids2-agent -f
