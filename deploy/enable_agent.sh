#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Enable Agent Service
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Enable Agent Service${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo -e "${YELLOW}Installing as user: $ACTUAL_USER${NC}"
echo -e "${YELLOW}Home directory: $ACTUAL_HOME${NC}"

# Determine project directory
PROJECT_DIR="$ACTUAL_HOME/ids2-soc-pipeline"

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Error: Project directory not found: $PROJECT_DIR${NC}"
    echo -e "${YELLOW}Please ensure the project is cloned to $PROJECT_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}Project directory: $PROJECT_DIR${NC}"

# Copy service file
echo -e "${YELLOW}Installing systemd service file...${NC}"
cp "$PROJECT_DIR/deploy/ids2-agent.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/ids2-agent.service

# Update service file with actual paths
sed -i "s|/home/pi/ids2-soc-pipeline|$PROJECT_DIR|g" /etc/systemd/system/ids2-agent.service
sed -i "s|User=pi|User=$ACTUAL_USER|g" /etc/systemd/system/ids2-agent.service
sed -i "s|Group=pi|Group=$ACTUAL_USER|g" /etc/systemd/system/ids2-agent.service

# Reload systemd
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload

# Enable service
echo -e "${YELLOW}Enabling IDS2 agent service...${NC}"
systemctl enable ids2-agent.service

# Check status
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Service enabled successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}To start the service:${NC}"
echo -e "  sudo systemctl start ids2-agent"
echo ""
echo -e "${YELLOW}To check status:${NC}"
echo -e "  sudo systemctl status ids2-agent"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo -e "  sudo journalctl -u ids2-agent -f"
echo ""
echo -e "${YELLOW}To stop the service:${NC}"
echo -e "  sudo systemctl stop ids2-agent"
echo ""
echo -e "${YELLOW}To disable the service:${NC}"
echo -e "  sudo systemctl disable ids2-agent"
echo ""
