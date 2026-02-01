#!/bin/bash
# ============================================================================
# Monitor OpenSearch Domain Creation Progress
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Monitoring OpenSearch Domain Creation${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""

# Check if process is running
if ! pgrep -f "create_opensearch_domain.py" > /dev/null; then
    echo -e "${YELLOW}No OpenSearch domain creation process found${NC}"
    exit 1
fi

echo -e "${YELLOW}Process is running. Monitoring progress...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop monitoring (process will continue in background)${NC}"
echo ""

# Monitor the process
while pgrep -f "create_opensearch_domain.py" > /dev/null; do
    sleep 5
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}OpenSearch Domain Creation Complete!${NC}"
echo -e "${GREEN}============================================================================${NC}"
