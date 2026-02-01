#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Docker Build Script
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Building Docker Images${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Build the IDS2 agent image
echo -e "${YELLOW}Building IDS2 Agent image...${NC}"
docker build -t ids2-agent:latest -f Dockerfile .

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Image built:${NC}"
docker images | grep ids2-agent

echo ""
echo -e "${YELLOW}To start the stack:${NC}"
echo -e "  cd docker && docker-compose up -d"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo -e "  docker-compose logs -f ids2-agent"
echo ""
