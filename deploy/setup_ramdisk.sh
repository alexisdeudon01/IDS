#!/bin/bash
# ============================================================================
# IDS2 SOC Pipeline - Setup RAM Disk for Logs
# Creates a tmpfs mount at /mnt/ram_logs for high-performance log storage
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}IDS2 SOC Pipeline - Setup RAM Disk${NC}"
echo -e "${GREEN}============================================================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Configuration
MOUNT_POINT="/mnt/ram_logs"
SIZE="512M"

echo -e "${YELLOW}RAM Disk Configuration:${NC}"
echo -e "  Mount point: $MOUNT_POINT"
echo -e "  Size: $SIZE"
echo ""

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    echo -e "${YELLOW}Creating mount point...${NC}"
    mkdir -p "$MOUNT_POINT"
    echo -e "${GREEN}✓ Mount point created${NC}"
else
    echo -e "${GREEN}✓ Mount point exists${NC}"
fi

# Check if already mounted
if mountpoint -q "$MOUNT_POINT"; then
    echo -e "${YELLOW}RAM disk already mounted at $MOUNT_POINT${NC}"
    echo -e "${YELLOW}Current usage:${NC}"
    df -h "$MOUNT_POINT"
    echo ""
    read -p "Remount? (yes/no): " remount
    
    if [ "$remount" = "yes" ]; then
        echo -e "${YELLOW}Unmounting...${NC}"
        umount "$MOUNT_POINT"
        echo -e "${GREEN}✓ Unmounted${NC}"
    else
        echo -e "${YELLOW}Keeping existing mount${NC}"
        exit 0
    fi
fi

# Mount tmpfs
echo -e "${YELLOW}Mounting tmpfs...${NC}"
mount -t tmpfs -o size=$SIZE,mode=1777 tmpfs "$MOUNT_POINT"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ RAM disk mounted successfully${NC}"
else
    echo -e "${RED}Error: Failed to mount RAM disk${NC}"
    exit 1
fi

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod 1777 "$MOUNT_POINT"
echo -e "${GREEN}✓ Permissions set (1777 - sticky bit + rwx for all)${NC}"

# Verify mount
echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}RAM Disk Setup Complete${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Mount information:${NC}"
df -h "$MOUNT_POINT"
echo ""
mount | grep "$MOUNT_POINT"
echo ""

# Add to /etc/fstab for persistence
echo -e "${YELLOW}Making mount persistent across reboots...${NC}"
FSTAB_ENTRY="tmpfs $MOUNT_POINT tmpfs defaults,size=$SIZE,mode=1777 0 0"

if grep -q "$MOUNT_POINT" /etc/fstab; then
    echo -e "${YELLOW}Entry already exists in /etc/fstab${NC}"
    read -p "Update entry? (yes/no): " update_fstab
    
    if [ "$update_fstab" = "yes" ]; then
        # Remove old entry
        sed -i "\|$MOUNT_POINT|d" /etc/fstab
        # Add new entry
        echo "$FSTAB_ENTRY" >> /etc/fstab
        echo -e "${GREEN}✓ /etc/fstab updated${NC}"
    fi
else
    echo "$FSTAB_ENTRY" >> /etc/fstab
    echo -e "${GREEN}✓ Added to /etc/fstab${NC}"
fi

echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${YELLOW}RAM disk is now available at: $MOUNT_POINT${NC}"
echo -e "${YELLOW}Size: $SIZE${NC}"
echo -e "${YELLOW}Persistent: Yes (will auto-mount on reboot)${NC}"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo -e "  - Suricata will write logs to: $MOUNT_POINT/eve.json"
echo -e "  - Vector will read logs from: $MOUNT_POINT/eve.json"
echo -e "  - Logs are stored in RAM (fast but volatile)"
echo -e "  - Logs will be lost on reboot (by design)"
echo ""
echo -e "${YELLOW}To check usage:${NC}"
echo -e "  df -h $MOUNT_POINT"
echo ""
echo -e "${YELLOW}To unmount:${NC}"
echo -e "  sudo umount $MOUNT_POINT"
echo ""
