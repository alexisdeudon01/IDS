#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Master Deployment & Testing Script
# ============================================================================

set -e

# Charger les variables d'environnement depuis .env
if [ -f .env ]; then
    while IFS='=' read -r key value; do
        if [[ ! -z "$key" && ! "$key" =~ ^# ]]; then
            export "$key=$value"
        fi
    done < .env
    echo -e "${GREEN}✅ Variables d'environnement chargées depuis .env${NC}"
else
    echo -e "${YELLOW}⚠️  Fichier .env non trouvé. Utilisation des variables d'environnement existantes ou des valeurs par défaut.${NC}"
fi

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

# Charger la configuration depuis config.yaml
# Note: Ce script bash ne peut pas directement lire config.yaml.
# Nous allons utiliser les variables d'environnement définies dans .env
# qui sont censées correspondre aux valeurs de config.yaml.
# Pour les tests, nous allons utiliser des valeurs par défaut ou des variables d'environnement.

# Récupérer les variables d'environnement ou utiliser des valeurs par défaut
PI_HOST="${RASPBERRY_PI_REMOTE_HOST:-192.168.178.66}"
PI_USER="${RASPBERRY_PI_REMOTE_USER:-pi}"
PROJECT_DIR="${PROJECT_ROOT:-/home/pi/ids2-soc-pipeline}" # Utilise PROJECT_ROOT défini plus haut

echo -e "${YELLOW}Checking connection to Raspberry Pi at ${PI_HOST}...${NC}"
if ! ping -c 1 $PI_HOST &> /dev/null; then
    echo -e "${RED}❌ Cannot reach Raspberry Pi at $PI_HOST${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Raspberry Pi is reachable${NC}"

echo -e "\n${YELLOW}Copying project files to Raspberry Pi...${NC}"

# Create project directory on Pi
ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} "mkdir -p ${PROJECT_DIR}"

# Copy all files, including .env, templates, and static directories
rsync -avz --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
    --exclude='venv/' \
    --exclude='docker/build.sh' \
    --exclude='docker/README.md' \
    --exclude='deploy/deploy_and_test.sh' \
    --exclude='deploy/create_opensearch_domain.sh' \
    --exclude='deploy/run_all_tests.py' \
    --exclude='deploy/monitor_opensearch_creation.sh' \
    --exclude='deploy/configure_fgac_via_aws.py' \
    --exclude='deploy/configure_opensearch_access.py' \
    --exclude='deploy/opensearch_thorough_tests.py' \
    --exclude='deploy/test_domain_creation.py' \
    --exclude='deploy/test_no_policy_access.py' \
    --exclude='deploy/test_opensearch_connection.py' \
    --exclude='deploy/vector_e2e_test.py' \
    --exclude='*.md' \
    --exclude='*.pdf' \
    --exclude='l.txt' \
    --exclude='opensearch describe-domain --domain-name ids2-soc-domain --profile moi33 --region us-east-1' \
    --exclude='.vscode/' \
    ./ ${PI_USER}@${PI_HOST}:${PROJECT_DIR}/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Files copied successfully${NC}"
else
    echo -e "${RED}❌ Failed to copy files${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Configuring Raspberry Pi environment...${NC}"

# Install Docker and Docker Compose on Pi
ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} << EOF
    sudo apt-get update && sudo apt-get install -y curl git python3-pip python3-venv
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ${PI_USER}
    sudo apt-get install -y docker-compose
    sudo systemctl enable docker
    sudo systemctl start docker
EOF

# Setup Python environment on Pi
ssh -o StrictHostKeyChecking=no ${PI_USER}@${PI_HOST} << EOF
    cd ${PROJECT_DIR}/python_env
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install awscli # Install AWS CLI for testing
EOF

echo -e "${GREEN}✅ Raspberry Pi environment configured${NC}"

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
echo -e "     ${GREEN}http://${PI_HOST}:3000${NC}"
echo -e "     Username: admin, Password: admin"
echo -e ""
echo -e "  7. Access Flask API Dashboard:"
echo -e "     ${GREEN}http://${PI_HOST}:5000${NC}"
echo -e ""

echo -e "${GREEN}============================================================================${NC}\n"
