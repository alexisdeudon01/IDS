#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Master Deployment & Testing Script
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Complete Deployment & Testing${NC}"
echo -e "${GREEN}============================================================================${NC}"

# ============================================================================
# PHASE 1: CREATE OPENSEARCH DOMAIN
# ============================================================================

echo -e "\n${BLUE}PHASE 1: Creating AWS OpenSearch Domain${NC}"
echo -e "${BLUE}============================================================================${NC}\n"

python3 deploy/create_opensearch_domain.py

if [ $? -ne 0 ]; then
    echo -e "\n${RED}❌ OpenSearch domain creation failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}✅ OpenSearch domain created successfully${NC}"

# ============================================================================
# PHASE 2: DEPLOY TO RASPBERRY PI
# ============================================================================

echo -e "\n${BLUE}PHASE 2: Deploying to Raspberry Pi${NC}"
echo -e "${BLUE}============================================================================${NC}\n"

PI_HOST="192.168.178.66"
PI_USER="pi"
PROJECT_DIR="/home/pi/ids2-soc-pipeline"

echo -e "${YELLOW}Checking connection to Raspberry Pi...${NC}"
if ! ping -c 1 $PI_HOST &> /dev/null; then
    echo -e "${RED}❌ Cannot reach Raspberry Pi at $PI_HOST${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Raspberry Pi is reachable${NC}"

echo -e "\n${YELLOW}Copying project files to Raspberry Pi...${NC}"

# Create project directory on Pi
ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} "mkdir -p ${PROJECT_DIR}"

# Copy all files
rsync -avz --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
    ./ ${PI_USER}@${PI_HOST}:${PROJECT_DIR}/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Files copied successfully${NC}"
else
    echo -e "${RED}❌ Failed to copy files${NC}"
    exit 1
fi

# ============================================================================
# PHASE 3: RUN ALL TESTS
# ============================================================================

echo -e "\n${BLUE}PHASE 3: Running Comprehensive Tests${NC}"
echo -e "${BLUE}============================================================================${NC}\n"

python3 deploy/run_all_tests.py

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${RED}❌ Some tests failed${NC}"
    exit 1
fi

# ============================================================================
# COMPLETION
# ============================================================================

echo -e "\n${GREEN}============================================================================${NC}"
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}============================================================================${NC}\n"

echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. SSH to Raspberry Pi:"
echo -e "     ${GREEN}ssh pi@192.168.178.66${NC}"
echo -e ""
echo -e "  2. Setup RAM disk:"
echo -e "     ${GREEN}sudo ./deploy/setup_ramdisk.sh${NC}"
echo -e ""
echo -e "  3. Install as service:"
echo -e "     ${GREEN}sudo ./deploy/enable_agent.sh${NC}"
echo -e ""
echo -e "  4. Start the agent:"
echo -e "     ${GREEN}sudo systemctl start ids2-agent${NC}"
echo -e ""
echo -e "  5. Monitor logs:"
echo -e "     ${GREEN}sudo journalctl -u ids2-agent -f${NC}"
echo -e ""
echo -e "  6. Access Grafana:"
echo -e "     ${GREEN}http://192.168.178.66:3000${NC}"
echo -e "     Username: admin, Password: admin"
echo -e ""

echo -e "${GREEN}============================================================================${NC}\n"
