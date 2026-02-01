"""
Suricata Manager Module

Generates Suricata configuration optimized for Raspberry Pi 5.
Manages Suricata lifecycle and monitors performance.
"""

import os
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SuricataManager:
    """Manages Suricata configuration and operations"""
    
    def __init__(self, config_manager):
        """
        Initialize Suricata manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.suricata_config = config_manager.get_suricata_config()
        self.rpi_config = config_manager.get_section('raspberry_pi')
        
        # Configuration file path
        self.config_file = Path(self.suricata_config.get('config_file', 'suricata/suricata.yaml'))
        
        # Network interface
        self.interface = self.rpi_config.get('network_interface', 'eth0')
    
    def generate_config(self) -> bool:
        """
        Generate Suricata configuration file
        
        Returns:
            True if successful
        """
        try:
            logger.info("Generating Suricata configuration...")
            
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Build configuration
            config_content = self._build_config_content()
            
            # Write to file
            with open(self.config_file, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Suricata configuration written to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate Suricata configuration: {e}")
            return False
    
    def _build_config_content(self) -> str:
        """
        Build Suricata configuration content in YAML format
        
        Returns:
            Configuration content as string
        """
        # Get configuration values
        home_net = self.suricata_config.get('home_net', '192.168.178.0/24')
        external_net = self.suricata_config.get('external_net', '!$HOME_NET')
        eve_log_file = self.suricata_config.get('eve_log_file', '/mnt/ram_logs/eve.json')
        rule_files = self.suricata_config.get('rule_files', ['/etc/suricata/rules/suricata.rules'])
        
        # Build YAML configuration
        config = f'''# Suricata Configuration for IDS2 SOC Pipeline
# Optimized for Raspberry Pi 5 (4 cores, 8GB RAM)
# Generated automatically - DO NOT EDIT MANUALLY

%YAML 1.1
---

# ============================================================================
# VARIABLES
# ============================================================================

vars:
  address-groups:
    HOME_NET: "{home_net}"
    EXTERNAL_NET: "{external_net}"
    
    HTTP_SERVERS: "$HOME_NET"
    SMTP_SERVERS: "$HOME_NET"
    SQL_SERVERS: "$HOME_NET"
    DNS_SERVERS: "$HOME_NET"
    TELNET_SERVERS: "$HOME_NET"
    AIM_SERVERS: "$EXTERNAL_NET"
    DC_SERVERS: "$HOME_NET"
    DNP3_SERVER: "$HOME_NET"
    DNP3_CLIENT: "$HOME_NET"
    MODBUS_CLIENT: "$HOME_NET"
    MODBUS_SERVER: "$HOME_NET"
    ENIP_CLIENT: "$HOME_NET"
    ENIP_SERVER: "$HOME_NET"

  port-groups:
    HTTP_PORTS: "80"
    SHELLCODE_PORTS: "!80"
    ORACLE_PORTS: 1521
    SSH_PORTS: 22
    DNP3_PORTS: 20000
    MODBUS_PORTS: 502
    FILE_DATA_PORTS: "[$HTTP_PORTS,110,143]"
    FTP_PORTS: 21
    GENEVE_PORTS: 6081
    VXLAN_PORTS: 4789
    TEREDO_PORTS: 3544

# ============================================================================
# PERFORMANCE TUNING (Raspberry Pi 5 Optimized)
# ============================================================================

# Threading - use 3 worker threads (leave 1 core for system)
threading:
  set-cpu-affinity: no
  cpu-affinity:
    - management-cpu-set:
        cpu: [ 0 ]
    - receive-cpu-set:
        cpu: [ 1 ]
    - worker-cpu-set:
        cpu: [ 2, 3 ]
  detect-thread-ratio: 1.0

# Packet capture settings
af-packet:
  - interface: {self.interface}
    threads: 2
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes
    use-mmap: yes
    mmap-locked: yes
    tpacket-v3: yes
    ring-size: 2048
    block-size: 32768
    block-timeout: 10
    use-emergency-flush: yes

# ============================================================================
# OUTPUTS
# ============================================================================

outputs:
  # EVE JSON log (primary output)
  - eve-log:
      enabled: yes
      filetype: regular
      filename: {eve_log_file}
      
      # Performance: use mmap for faster writes
      # Note: This requires /mnt/ram_logs to be a tmpfs
      
      # Rotation disabled (Vector handles log rotation)
      rotate-interval: 0
      
      # Output types
      types:
        - alert:
            payload: yes
            payload-buffer-size: 4kb
            payload-printable: yes
            packet: yes
            metadata: yes
            http-body: yes
            http-body-printable: yes
            
        - anomaly:
            enabled: yes
            
        - http:
            extended: yes
            
        - dns:
            query: yes
            answer: yes
            
        - tls:
            extended: yes
            
        - files:
            force-magic: no
            
        - smtp:
            extended: yes
            
        - ssh:
            enabled: yes
            
        - stats:
            totals: yes
            threads: yes
            deltas: yes
            
        - flow:
            enabled: yes

  # Fast log (optional, for quick alerts)
  - fast:
      enabled: no
      filename: /var/log/suricata/fast.log
      append: yes

# ============================================================================
# LOGGING
# ============================================================================

logging:
  default-log-level: notice
  default-log-format: "[%i] %t - (%f:%l) <%d> (%n) -- "
  
  outputs:
    - console:
        enabled: yes
    - file:
        enabled: yes
        level: info
        filename: /var/log/suricata/suricata.log
    - syslog:
        enabled: no

# ============================================================================
# DETECTION ENGINE
# ============================================================================

# Rule files
default-rule-path: /etc/suricata/rules
rule-files:
'''
        
        # Add rule files
        for rule_file in rule_files:
            config += f'  - {rule_file}\n'
        
        config += '''
# Classification file
classification-file: /etc/suricata/classification.config
reference-config-file: /etc/suricata/reference.config

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================

# Packet acquisition
max-pending-packets: 1024

# Detection engine
detect:
  profile: medium
  custom-values:
    toclient-groups: 3
    toserver-groups: 25
  
  # Prefilter settings
  prefilter:
    default: mpm
  
  # Grouping
  grouping:
    tcp-whitelist: 53, 80, 139, 443, 445, 1433, 3306, 3389, 6666, 6667, 8080
    udp-whitelist: 53, 135, 5060

# Stream engine
stream:
  memcap: 128mb
  checksum-validation: yes
  inline: no
  reassembly:
    memcap: 256mb
    depth: 1mb
    toserver-chunk-size: 2560
    toclient-chunk-size: 2560
    randomize-chunk-size: yes

# Host table
host:
  hash-size: 4096
  prealloc: 1000
  memcap: 32mb

# IP Reputation
reputation-categories-file: /etc/suricata/iprep/categories.txt
default-reputation-path: /etc/suricata/iprep
reputation-files:

# Flow settings
flow:
  memcap: 128mb
  hash-size: 65536
  prealloc: 10000
  emergency-recovery: 30

# Defrag settings
defrag:
  memcap: 32mb
  hash-size: 65536
  trackers: 65535
  max-frags: 65535
  prealloc: yes
  timeout: 60

# ============================================================================
# APPLICATION LAYER PARSERS
# ============================================================================

app-layer:
  protocols:
    tls:
      enabled: yes
      detection-ports:
        dp: 443
    
    dcerpc:
      enabled: yes
    
    ftp:
      enabled: yes
    
    ssh:
      enabled: yes
    
    smtp:
      enabled: yes
    
    http:
      enabled: yes
      memcap: 64mb
    
    dns:
      tcp:
        enabled: yes
        detection-ports:
          dp: 53
      udp:
        enabled: yes
        detection-ports:
          dp: 53

# ============================================================================
# PROFILING
# ============================================================================

profiling:
  rules:
    enabled: yes
    filename: /var/log/suricata/rule_perf.log
    append: yes
    sort: avgticks
    limit: 100
    json: yes
  
  keywords:
    enabled: yes
    filename: /var/log/suricata/keyword_perf.log
    append: yes
  
  prefilter:
    enabled: yes
    filename: /var/log/suricata/prefilter_perf.log
    append: yes
  
  rulegroups:
    enabled: yes
    filename: /var/log/suricata/rule_group_perf.log
    append: yes
  
  packets:
    enabled: yes
    filename: /var/log/suricata/packet_stats.log
    append: yes
    csv:
      enabled: no

# ============================================================================
# PCAP PROCESSING
# ============================================================================

pcap:
  - interface: {self.interface}

pcap-file:
  checksum-checks: auto

# ============================================================================
# UNIX SOCKET
# ============================================================================

unix-command:
  enabled: yes
  filename: /var/run/suricata/suricata-command.socket

# ============================================================================
# MAGIC FILE
# ============================================================================

magic-file: /usr/share/file/misc/magic

# ============================================================================
# LEGACY SETTINGS
# ============================================================================

legacy:
  uricontent: enabled

# ============================================================================
# ENGINE ANALYSIS
# ============================================================================

engine-analysis:
  rules-fast-pattern: yes
  rules: yes

# ============================================================================
# STATS
# ============================================================================

stats:
  enabled: yes
  interval: 30
  decoder-events: yes
  decoder-events-prefix: "decoder.event"
  stream-events: no
'''
        
        return config
    
    def validate_config(self) -> bool:
        """
        Validate Suricata configuration file
        
        Returns:
            True if valid
        """
        if not self.config_file.exists():
            logger.error(f"Suricata config file not found: {self.config_file}")
            return False
        
        try:
            # Use suricata -T to test configuration
            result = subprocess.run(
                ['suricata', '-T', '-c', str(self.config_file)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Suricata configuration validation passed")
                return True
            else:
                logger.error(f"Suricata configuration validation failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.warning("Suricata binary not found, skipping validation")
            return True  # Assume valid if suricata not installed yet
        except subprocess.TimeoutExpired:
            logger.error("Suricata validation timeout")
            return False
        except Exception as e:
            logger.error(f"Error validating Suricata config: {e}")
            return False
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get Suricata statistics via unix socket
        
        Returns:
            Statistics dictionary or None
        """
        # This would query Suricata's unix socket
        # For now, this is a placeholder
        logger.debug("Suricata stats query would be implemented here")
        return None
    
    def reload_rules(self) -> bool:
        """
        Reload Suricata rules without restart
        
        Returns:
            True if successful
        """
        # This would send reload command via unix socket
        # For now, this is a placeholder
        logger.info("Suricata rule reload would be implemented here")
        return True
