#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Network Configuration (eth0 ONLY)
# Disables all network interfaces except eth0
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Network Configuration (eth0 ONLY)${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will disable ALL network interfaces except eth0${NC}"
echo -e "${YELLOW}Make sure you are connected via eth0 or you will lose connectivity!${NC}"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Current network interfaces:${NC}"
ip link show

echo ""
echo -e "${YELLOW}Configuring network interfaces...${NC}"

# Ensure eth0 is UP
if ip link show eth0 &>/dev/null; then
    echo -e "${GREEN}✓ eth0 found${NC}"
    ip link set eth0 up
    echo -e "${GREEN}✓ eth0 is UP${NC}"
else
    echo -e "${RED}Error: eth0 not found!${NC}"
    exit 1
fi

# Disable wlan0 (WiFi)
if ip link show wlan0 &>/dev/null; then
    echo -e "${YELLOW}Disabling wlan0...${NC}"
    ip link set wlan0 down
    echo -e "${GREEN}✓ wlan0 disabled${NC}"
else
    echo -e "${YELLOW}wlan0 not found (already disabled or not present)${NC}"
fi

# Disable usb0 (USB networking)
if ip link show usb0 &>/dev/null; then
    echo -e "${YELLOW}Disabling usb0...${NC}"
    ip link set usb0 down
    echo -e "${GREEN}✓ usb0 disabled${NC}"
else
    echo -e "${YELLOW}usb0 not found (already disabled or not present)${NC}"
fi

# Disable any other interfaces (except lo and eth0)
for iface in $(ip link show | grep -oP '^\d+: \K[^:]+' | grep -v '^lo$' | grep -v '^eth0$'); do
    echo -e "${YELLOW}Disabling $iface...${NC}"
    ip link set "$iface" down
    echo -e "${GREEN}✓ $iface disabled${NC}"
done

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Network Configuration Complete${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Active interfaces:${NC}"
ip link show | grep -E '^[0-9]+:' | grep 'state UP'

echo ""
echo -e "${YELLOW}To make this persistent across reboots, create a systemd service:${NC}"
echo -e "  sudo cp deploy/network-eth0-only.service /etc/systemd/system/"
echo -e "  sudo systemctl enable network-eth0-only.service"
echo ""
