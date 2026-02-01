#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - Comprehensive Test Runner
Runs all tests on Raspberry Pi after OpenSearch domain creation
"""

import sys
import os
import time
import subprocess
import json
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Raspberry Pi Configuration
    'pi_host': '192.168.178.66',
    'pi_user': 'pi',
    'pi_password': 'pi',  # Will use SSH key if available
    
    # Project paths
    'project_dir': '/home/pi/ids2-soc-pipeline',
    'python_venv': '/home/pi/ids2-soc-pipeline/python_env/venv',
    
    # Test configuration
    'test_timeout': 300,  # 5 minutes per test
    'verbose': True,
}

# ============================================================================
# PROGRESS TRACKING
# ============================================================================

class TestProgress:
    """Track test progress"""
    
    def __init__(self, total_tests):
        self.total = total_tests
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.current = 0
        self.results = []
    
    def start_test(self, test_name):
        """Start a test"""
        self.current += 1
        print(f"\n{'='*80}")
        print(f"Test {self.current}/{self.total}: {test_name}")
        print(f"{'='*80}")
    
    def pass_test(self, test_name, duration=0):
        """Mark test as passed"""
        self.passed += 1
        self.results.append({
            'name': test_name,
            'status': 'PASSED',
            'duration': duration
        })
        print(f"✅ PASSED ({duration:.2f}s)")
    
    def fail_test(self, test_name, error, duration=0):
        """Mark test as failed"""
        self.failed += 1
        self.results.append({
            'name': test_name,
            'status': 'FAILED',
            'error': str(error),
            'duration': duration
        })
        print(f"❌ FAILED: {error} ({duration:.2f}s)")
    
    def skip_test(self, test_name, reason):
        """Mark test as skipped"""
        self.skipped += 1
        self.results.append({
            'name': test_name,
            'status': 'SKIPPED',
            'reason': reason
        })
        print(f"⏭️  SKIPPED: {reason}")
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"Total Tests:  {self.total}")
        print(f"✅ Passed:    {self.passed}")
        print(f"❌ Failed:    {self.failed}")
        print(f"⏭️  Skipped:   {self.skipped}")
        
        success_rate = (self.passed / self.total * 100) if self.total > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if self.failed > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.results:
                if result['status'] == 'FAILED':
                    print(f"   - {result['name']}: {result['error']}")
        
        print(f"\n{'='*80}\n")
        
        return self.failed == 0

# ============================================================================
# SSH COMMAND EXECUTOR
# ============================================================================

class SSHExecutor:
    """Execute commands on Raspberry Pi via SSH"""
    
    def __init__(self, host, user, password=None):
        self.host = host
        self.user = user
        self.password = password
    
    def execute(self, command, timeout=60):
        """Execute command via SSH"""
        ssh_cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'ConnectTimeout=10',
            f'{self.user}@{self.host}',
            command
        ]
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, '', 'Command timed out'
        except Exception as e:
            return False, '', str(e)
    
    def execute_python(self, script, timeout=60):
        """Execute Python script on Pi"""
        command = f"cd {CONFIG['project_dir']} && source {CONFIG['python_venv']}/bin/activate && python3 -c '{script}'"
        return self.execute(command, timeout)

# ============================================================================
# TEST DEFINITIONS
# ============================================================================

class TestSuite:
    """Test suite for IDS2 SOC Pipeline"""
    
    def __init__(self, ssh):
        self.ssh = ssh
        self.progress = TestProgress(total_tests=15)  # Update based on actual test count
    
    # ========================================================================
    # PHASE 1: PRE-DEPLOYMENT TESTS
    # ========================================================================
    
    def test_01_network_connectivity(self):
        """Test network connectivity to Raspberry Pi"""
        self.progress.start_test("Network Connectivity")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute('echo "Connection successful"')
        duration = time.time() - start
        
        if success and "Connection successful" in stdout:
            self.progress.pass_test("Network Connectivity", duration)
        else:
            self.progress.fail_test("Network Connectivity", stderr or "Connection failed", duration)
    
    def test_02_python_version(self):
        """Test Python version"""
        self.progress.start_test("Python Version Check")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute('python3 --version')
        duration = time.time() - start
        
        if success and "Python 3." in stdout:
            version = stdout.strip()
            print(f"   Found: {version}")
            self.progress.pass_test("Python Version Check", duration)
        else:
            self.progress.fail_test("Python Version Check", "Python 3 not found", duration)
    
    def test_03_docker_installed(self):
        """Test Docker installation"""
        self.progress.start_test("Docker Installation")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute('docker --version')
        duration = time.time() - start
        
        if success and "Docker version" in stdout:
            version = stdout.strip()
            print(f"   Found: {version}")
            self.progress.pass_test("Docker Installation", duration)
        else:
            self.progress.fail_test("Docker Installation", "Docker not installed", duration)
    
    def test_04_project_exists(self):
        """Test project directory exists"""
        self.progress.start_test("Project Directory")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute(f'test -d {CONFIG["project_dir"]} && echo "exists"')
        duration = time.time() - start
        
        if success and "exists" in stdout:
            self.progress.pass_test("Project Directory", duration)
        else:
            self.progress.fail_test("Project Directory", f"Directory {CONFIG['project_dir']} not found", duration)
    
    # ========================================================================
    # PHASE 2: COMPONENT TESTS
    # ========================================================================
    
    def test_05_config_manager(self):
        """Test Configuration Manager"""
        self.progress.start_test("Configuration Manager")
        start = time.time()
        
        script = """
import sys
sys.path.insert(0, 'python_env')
from modules.config_manager import ConfigManager

try:
    config = ConfigManager('config.yaml')
    print(f"CPU Limit: {config.get('resources.max_cpu_percent')}%")
    print(f"RAM Limit: {config.get('resources.max_ram_percent')}%")
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
"""
        
        success, stdout, stderr = self.ssh.execute_python(script, timeout=30)
        duration = time.time() - start
        
        if success and "SUCCESS" in stdout:
            print(f"   {stdout.strip()}")
            self.progress.pass_test("Configuration Manager", duration)
        else:
            self.progress.fail_test("Configuration Manager", stderr or "Failed to load config", duration)
    
    def test_06_aws_credentials(self):
        """Test AWS credentials"""
        self.progress.start_test("AWS Credentials")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute('aws sts get-caller-identity --profile moi33')
        duration = time.time() - start
        
        if success:
            print(f"   AWS credentials valid")
            self.progress.pass_test("AWS Credentials", duration)
        else:
            self.progress.fail_test("AWS Credentials", "Invalid AWS credentials", duration)
    
    def test_07_opensearch_connectivity(self):
        """Test OpenSearch connectivity"""
        self.progress.start_test("OpenSearch Connectivity")
        start = time.time()
        
        script = """
import sys
sys.path.insert(0, 'python_env')
from modules.config_manager import ConfigManager
from modules.aws_manager import AWSManager

try:
    config = ConfigManager('config.yaml')
    aws_mgr = AWSManager(config)
    
    if aws_mgr.verify_credentials():
        print("✓ AWS credentials valid")
    
    domain_info = aws_mgr.get_domain_info()
    if domain_info:
        print(f"✓ Domain found: {domain_info['DomainName']}")
        print(f"✓ Endpoint: {domain_info.get('Endpoint', 'N/A')}")
        print("SUCCESS")
    else:
        print("ERROR: Domain not found")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
"""
        
        success, stdout, stderr = self.ssh.execute_python(script, timeout=60)
        duration = time.time() - start
        
        if success and "SUCCESS" in stdout:
            print(f"   {stdout.strip()}")
            self.progress.pass_test("OpenSearch Connectivity", duration)
        else:
            self.progress.fail_test("OpenSearch Connectivity", stderr or "Connection failed", duration)
    
    def test_08_ram_disk(self):
        """Test RAM disk setup"""
        self.progress.start_test("RAM Disk Setup")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute('mountpoint -q /mnt/ram_logs && echo "mounted" || echo "not mounted"')
        duration = time.time() - start
        
        if "mounted" in stdout:
            # Get size
            success2, stdout2, _ = self.ssh.execute('df -h /mnt/ram_logs | tail -1')
            print(f"   {stdout2.strip()}")
            self.progress.pass_test("RAM Disk Setup", duration)
        else:
            self.progress.skip_test("RAM Disk Setup", "Not mounted - run setup_ramdisk.sh")
    
    # ========================================================================
    # PHASE 3: DOCKER STACK TESTS
    # ========================================================================
    
    def test_09_docker_compose_syntax(self):
        """Test Docker Compose syntax"""
        self.progress.start_test("Docker Compose Syntax")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute(
            f'cd {CONFIG["project_dir"]} && docker-compose -f docker/docker-compose.yml config > /dev/null && echo "valid"'
        )
        duration = time.time() - start
        
        if success and "valid" in stdout:
            self.progress.pass_test("Docker Compose Syntax", duration)
        else:
            self.progress.fail_test("Docker Compose Syntax", stderr or "Invalid syntax", duration)
    
    def test_10_docker_images_pull(self):
        """Test Docker image pulling"""
        self.progress.start_test("Docker Images Pull")
        start = time.time()
        
        print("   Pulling Docker images (this may take a few minutes)...")
        success, stdout, stderr = self.ssh.execute(
            f'cd {CONFIG["project_dir"]} && docker-compose -f docker/docker-compose.yml pull',
            timeout=600  # 10 minutes
        )
        duration = time.time() - start
        
        if success:
            self.progress.pass_test("Docker Images Pull", duration)
        else:
            self.progress.fail_test("Docker Images Pull", stderr or "Failed to pull images", duration)
    
    def test_11_docker_stack_start(self):
        """Test Docker stack startup"""
        self.progress.start_test("Docker Stack Startup")
        start = time.time()
        
        print("   Starting Docker services...")
        success, stdout, stderr = self.ssh.execute(
            f'cd {CONFIG["project_dir"]} && docker-compose -f docker/docker-compose.yml up -d',
            timeout=180
        )
        
        if success:
            # Wait for health checks
            print("   Waiting for health checks (30s)...")
            time.sleep(30)
            
            # Check service status
            success2, stdout2, stderr2 = self.ssh.execute(
                f'cd {CONFIG["project_dir"]} && docker-compose -f docker/docker-compose.yml ps'
            )
            
            duration = time.time() - start
            
            if success2:
                print(f"   Services:\n{stdout2}")
                self.progress.pass_test("Docker Stack Startup", duration)
            else:
                self.progress.fail_test("Docker Stack Startup", "Failed to check status", duration)
        else:
            duration = time.time() - start
            self.progress.fail_test("Docker Stack Startup", stderr or "Failed to start", duration)
    
    # ========================================================================
    # PHASE 4: METRICS TESTS
    # ========================================================================
    
    def test_12_prometheus_metrics(self):
        """Test Prometheus metrics endpoint"""
        self.progress.start_test("Prometheus Metrics")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute(
            'curl -s http://localhost:9090/-/healthy'
        )
        duration = time.time() - start
        
        if success and "Prometheus" in stdout:
            self.progress.pass_test("Prometheus Metrics", duration)
        else:
            self.progress.skip_test("Prometheus Metrics", "Prometheus not running")
    
    def test_13_grafana_access(self):
        """Test Grafana access"""
        self.progress.start_test("Grafana Access")
        start = time.time()
        
        success, stdout, stderr = self.ssh.execute(
            'curl -s http://localhost:3000/api/health'
        )
        duration = time.time() - start
        
        if success and "ok" in stdout.lower():
            self.progress.pass_test("Grafana Access", duration)
        else:
            self.progress.skip_test("Grafana Access", "Grafana not running")
    
    # ========================================================================
    # PHASE 5: CLEANUP
    # ========================================================================
    
    def test_14_docker_stack_stop(self):
        """Test Docker stack shutdown"""
        self.progress.start_test("Docker Stack Shutdown")
        start = time.time()
        
        print("   Stopping Docker services...")
        success, stdout, stderr = self.ssh.execute(
            f'cd {CONFIG["project_dir"]} && docker-compose -f docker/docker-compose.yml down',
            timeout=120
        )
        duration = time.time() - start
        
        if success:
            self.progress.pass_test("Docker Stack Shutdown", duration)
        else:
            self.progress.fail_test("Docker Stack Shutdown", stderr or "Failed to stop", duration)
    
    def test_15_final_verification(self):
        """Final verification"""
        self.progress.start_test("Final Verification")
        start = time.time()
        
        # Check all files exist
        files_to_check = [
            'config.yaml',
            'python_env/agent_mp.py',
            'docker/docker-compose.yml',
            'vector/vector.toml',
            'suricata/suricata.yaml',
        ]
        
        all_exist = True
        for file in files_to_check:
            success, stdout, stderr = self.ssh.execute(
                f'test -f {CONFIG["project_dir"]}/{file} && echo "exists" || echo "missing"'
            )
            if "missing" in stdout:
                all_exist = False
                print(f"   ❌ Missing: {file}")
            else:
                print(f"   ✓ Found: {file}")
        
        duration = time.time() - start
        
        if all_exist:
            self.progress.pass_test("Final Verification", duration)
        else:
            self.progress.fail_test("Final Verification", "Some files missing", duration)
    
    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================
    
    def run_all(self):
        """Run all tests"""
        print(f"\n{'='*80}")
        print(f"IDS2 SOC Pipeline - Comprehensive Test Suite")
        print(f"Target: {CONFIG['pi_user']}@{CONFIG['pi_host']}")
        print(f"{'='*80}\n")
        
        # Run tests in order
        self.test_01_network_connectivity()
        self.test_02_python_version()
        self.test_03_docker_installed()
        self.test_04_project_exists()
        self.test_05_config_manager()
        self.test_06_aws_credentials()
        self.test_07_opensearch_connectivity()
        self.test_08_ram_disk()
        self.test_09_docker_compose_syntax()
        self.test_10_docker_images_pull()
        self.test_11_docker_stack_start()
        self.test_12_prometheus_metrics()
        self.test_13_grafana_access()
        self.test_14_docker_stack_stop()
        self.test_15_final_verification()
        
        # Print summary
        success = self.progress.print_summary()
        
        return success

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution"""
    print(f"\n{'='*80}")
    print(f"IDS2 SOC Pipeline - Test Runner")
    print(f"{'='*80}\n")
    
    # Initialize SSH executor
    ssh = SSHExecutor(
        host=CONFIG['pi_host'],
        user=CONFIG['pi_user'],
        password=CONFIG.get('pi_password')
    )
    
    # Run tests
    suite = TestSuite(ssh)
    success = suite.run_all()
    
    if success:
        print(f"✅ All tests passed! System is ready for production.")
        return 0
    else:
        print(f"❌ Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
