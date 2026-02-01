#!/usr/bin/env python3
"""
IDS2 SOC Pipeline - Multi-Process Orchestration Agent

This is the main entry point for the IDS2 SOC pipeline.
It orchestrates all components using a multi-process architecture:

Process #1: Supervisor (this process)
Process #2: Resource Controller (CPU/RAM monitoring + throttling)
Process #3: Connectivity Checker (async DNS/TLS/OpenSearch tests)
Process #4: Metrics Server (Prometheus exporter)
Process #5: Verification (optional - verifies ingestion)

The supervisor manages the lifecycle of all child processes and
coordinates the pipeline deployment phases.
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from multiprocessing import Manager, Event

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.config_manager import ConfigManager
from modules.resource_controller import ResourceController
from modules.connectivity_async import ConnectivityChecker
from modules.metrics_server import MetricsServer
from modules.aws_manager import AWSManager
from modules.docker_manager import DockerManager
from modules.vector_manager import VectorManager
from modules.suricata_manager import SuricataManager
from modules.git_workflow import GitWorkflow
from modules.api_server import APIServer # Nouvelle importation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


class IDS2Agent:
    """
    Multi-Process IDS2 SOC Pipeline Agent
    
    This is the supervisor process that manages all child processes
    and orchestrates the pipeline deployment.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize IDS2 Agent
        
        Args:
            config_path: Path to configuration file
        """
        logger.info("=" * 80)
        logger.info("IDS2 SOC Pipeline - Multi-Process Agent")
        logger.info("=" * 80)
        
        # Load configuration
        try:
            self.config = ConfigManager(config_path)
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
        
        # Create shared state using multiprocessing.Manager()
        self.manager = Manager()
        self.shared_state = self.manager.dict()
        
        # Initialize shared state
        self._init_shared_state()
        
        # Initialize managers
        self.resource_controller = ResourceController(self.config, self.shared_state)
        self.connectivity_checker = ConnectivityChecker(self.config, self.shared_state)
        self.metrics_server = MetricsServer(self.config, self.shared_state)
        self.aws_manager = AWSManager(self.config)
        self.docker_manager = DockerManager(self.config)
        self.vector_manager = VectorManager(self.config)
        self.suricata_manager = SuricataManager(self.config)
        self.git_workflow = GitWorkflow(self.config)
        self.api_server = APIServer(
            self.config,
            self.shared_state,
            self.docker_manager, # Passer DockerManager
            self.suricata_manager # Passer SuricataManager
        ) # Initialisation de l'API Flask
        
        # Shutdown event
        self.shutdown_event = Event()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("IDS2 Agent initialized")
    
    def _init_shared_state(self) -> None:
        """Initialize shared state dictionary"""
        # Resource metrics
        self.shared_state['cpu_percent'] = 0.0
        self.shared_state['ram_percent'] = 0.0
        self.shared_state['throttle_level'] = 0
        self.shared_state['resource_ok'] = True
        
        # Connectivity status
        self.shared_state['dns_ok'] = False
        self.shared_state['tls_ok'] = False
        self.shared_state['opensearch_ok'] = False
        self.shared_state['aws_ready'] = False
        self.shared_state['opensearch_endpoint'] = self.config.get('aws.opensearch_endpoint')
        
        # Service status
        self.shared_state['vector_running'] = False
        self.shared_state['suricata_running'] = False
        self.shared_state['redis_running'] = False
        self.shared_state['api_server_running'] = False # Nouvel état pour l'API Flask
        self.shared_state['pipeline_ok'] = False
        
        # Counters
        self.shared_state['events_processed'] = 0
        self.shared_state['events_failed'] = 0
        
        logger.debug("Shared state initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    def _start_child_processes(self) -> bool:
        """
        Start all child processes
        
        Returns:
            True if all processes started successfully
        """
        logger.info("Starting child processes...")
        
        try:
            # Start Process #2: Resource Controller
            logger.info("Starting Resource Controller (Process #2)...")
            self.resource_controller.start()
            time.sleep(1)  # Give it time to start
            
            if not self.resource_controller.is_alive():
                logger.error("Resource Controller failed to start")
                return False
            
            # Start Process #3: Connectivity Checker
            logger.info("Starting Connectivity Checker (Process #3)...")
            self.connectivity_checker.start()
            time.sleep(1)
            
            if not self.connectivity_checker.is_alive():
                logger.error("Connectivity Checker failed to start")
                return False
            
            # Start Process #4: Metrics Server
            logger.info("Starting Metrics Server (Process #4)...")
            self.metrics_server.start()
            time.sleep(1)
            
            if not self.metrics_server.is_alive():
                logger.error("Metrics Server failed to start")
                return False
            
            # Start Process #5: API Server
            logger.info("Starting API Server (Process #5)...")
            self.api_server.start()
            time.sleep(1)

            if not self.api_server.is_alive():
                logger.error("API Server failed to start")
                return False
            self.shared_state['api_server_running'] = True
            
            logger.info("All child processes started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start child processes: {e}")
            return False
    
    def _stop_child_processes(self) -> None:
        """Stop all child processes gracefully"""
        logger.info("Stopping child processes...")
        
        # Stop in reverse order
        if self.api_server.is_alive():
            logger.info("Stopping API Server...")
            self.api_server.stop()

        if self.metrics_server.is_alive():
            logger.info("Stopping Metrics Server...")
            self.metrics_server.stop()
        
        if self.connectivity_checker.is_alive():
            logger.info("Stopping Connectivity Checker...")
            self.connectivity_checker.stop()
        
        if self.resource_controller.is_alive():
            logger.info("Stopping Resource Controller...")
            self.resource_controller.stop()
        
        logger.info("All child processes stopped")
    
    def _verify_git_branch(self) -> bool:
        """
        Verify we're on the correct Git branch
        
        Returns:
            True if on correct branch
        """
        logger.info("Verifying Git branch...")
        
        # Note: In worktree setup, we may be on a different branch
        # For now, we'll just log the current branch
        current_branch = self.git_workflow.get_current_branch()
        required_branch = self.git_workflow.required_branch
        
        if current_branch:
            logger.info(f"Current branch: {current_branch}")
            if current_branch != required_branch:
                logger.warning(
                    f"Not on required branch '{required_branch}'. "
                    f"This may be a worktree setup."
                )
        else:
            logger.warning("Could not determine current branch")
        
        return True  # Don't fail on branch check in worktree setup
    
    def _phase_a_verify_aws(self) -> bool:
        """
        Phase A: Verify AWS credentials and OpenSearch domain
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE A: AWS Verification")
        logger.info("=" * 80)
        
        # Verify AWS credentials
        logger.info("Verifying AWS credentials...")
        if not self.aws_manager.verify_credentials():
            logger.error("AWS credentials verification failed")
            return False
        
        # Get domain configuration
        domain_name = self.config.get('aws.opensearch_domain')
        if not domain_name:
            logger.error("No OpenSearch domain configured")
            return False
        
        # Verify domain exists
        logger.info(f"Verifying OpenSearch domain: {domain_name}")
        if not self.aws_manager.verify_domain_exists(domain_name):
            logger.error(f"OpenSearch domain '{domain_name}' not found or not ready")
            return False
        
        # Get domain endpoint
        endpoint = self.aws_manager.get_domain_endpoint(domain_name)
        if not endpoint:
            logger.error("Could not get OpenSearch endpoint")
            return False
        
        logger.info(f"OpenSearch endpoint: {endpoint}")

        # Share endpoint for connectivity checks
        self.shared_state['opensearch_endpoint'] = endpoint
        
        # Update config with endpoint if not set
        if not self.config.get('aws.opensearch_endpoint'):
            logger.info("Updating configuration with OpenSearch endpoint")
            # Note: This would require config update functionality
        
        logger.info("Phase A completed successfully")
        return True
    
    def _phase_b_generate_configs(self) -> bool:
        """
        Phase B: Generate Suricata and Vector configurations
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE B: Configuration Generation")
        logger.info("=" * 80)
        
        # Generate Suricata configuration
        logger.info("Generating Suricata configuration...")
        if not self.suricata_manager.generate_config():
            logger.error("Failed to generate Suricata configuration")
            return False
        
        # Validate Suricata configuration
        if not self.suricata_manager.validate_config():
            logger.warning("Suricata configuration validation failed (may be OK if not installed)")
        
        # Generate Vector configuration
        logger.info("Generating Vector configuration...")
        if not self.vector_manager.generate_config():
            logger.error("Failed to generate Vector configuration")
            return False
        
        # Validate Vector configuration
        if not self.vector_manager.validate_config():
            logger.error("Vector configuration validation failed")
            return False
        
        logger.info("Phase B completed successfully")
        return True
    
    def _phase_c_start_docker(self) -> bool:
        """
        Phase C: Start Docker Compose stack
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE C: Docker Stack Deployment")
        logger.info("=" * 80)
        
        # Verify docker-compose.yml exists
        if not self.docker_manager.verify_compose_file():
            logger.error("Docker Compose file validation failed")
            return False
        
        # Start Docker stack
        logger.info("Starting Docker Compose stack...")
        if not self.docker_manager.start_stack(pull=True):
            logger.error("Failed to start Docker stack")
            return False
        
        # Wait for stack to be healthy
        logger.info("Waiting for Docker stack to be healthy...")
        if not self.docker_manager.wait_for_stack_healthy(max_wait=120):
            logger.error("Docker stack failed to become healthy")
            return False
        
        # Update shared state
        stack_status = self.docker_manager.get_stack_status()
        self.shared_state['vector_running'] = stack_status.get('vector', False)
        self.shared_state['redis_running'] = stack_status.get('redis', False)
        
        logger.info("Phase C completed successfully")
        return True
    
    def _phase_d_wait_connectivity(self) -> bool:
        """
        Phase D: Wait for AWS connectivity
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE D: Connectivity Verification")
        logger.info("=" * 80)
        
        # Wait for connectivity checker to complete first check
        logger.info("Waiting for connectivity checks...")
        max_wait = 120
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait:
            if self.shared_state.get('aws_ready', False):
                logger.info("AWS connectivity verified")
                return True
            
            # Log current status
            dns_ok = self.shared_state.get('dns_ok', False)
            tls_ok = self.shared_state.get('tls_ok', False)
            opensearch_ok = self.shared_state.get('opensearch_ok', False)
            
            logger.info(
                f"Connectivity status - DNS: {dns_ok}, TLS: {tls_ok}, "
                f"OpenSearch: {opensearch_ok}"
            )
            
            time.sleep(10)
        
        logger.error("Timeout waiting for AWS connectivity")
        return False
    
    def _phase_e_verify_pipeline(self) -> bool:
        """
        Phase E: Verify pipeline is operational
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE E: Pipeline Verification")
        logger.info("=" * 80)
        
        # Check all services are running
        stack_status = self.docker_manager.get_stack_status()
        
        all_running = all(stack_status.values())
        if not all_running:
            logger.error(f"Not all services running: {stack_status}")
            return False
        
        # Check AWS connectivity
        if not self.shared_state.get('aws_ready', False):
            logger.error("AWS not ready")
            return False
        
        # Check resource usage is within limits
        if not self.shared_state.get('resource_ok', True):
            logger.warning("Resource usage exceeds limits")
        
        # Update pipeline status
        self.shared_state['pipeline_ok'] = True
        
        logger.info("Phase E completed successfully")
        logger.info("Pipeline is operational!")
        return True
    
    def _phase_f_commit_changes(self) -> bool:
        """
        Phase F: Commit and push configuration changes
        
        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("PHASE F: Git Commit")
        logger.info("=" * 80)
        
        # Check if there are changes
        if not self.git_workflow.has_changes():
            logger.info("No changes to commit")
            return True
        
        # Commit and push
        commit_message = "chore(dev): IDS2 agent bootstrap - configs generated"
        logger.info(f"Committing changes: {commit_message}")
        
        if not self.git_workflow.commit_and_push(commit_message):
            logger.warning("Failed to commit changes (continuing anyway)")
            # Don't fail the deployment if git fails
        
        logger.info("Phase F completed")
        return True
    
    def _phase_g_monitor(self) -> None:
        """
        Phase G: Monitor pipeline operation
        
        This runs indefinitely until shutdown signal.
        """
        logger.info("=" * 80)
        logger.info("PHASE G: Monitoring")
        logger.info("=" * 80)
        logger.info("Pipeline is running. Press Ctrl+C to stop.")
        logger.info("Metrics available at: http://localhost:9100/metrics")
        logger.info("=" * 80)
        
        try:
            while not self.shutdown_event.is_set():
                # Monitor child processes
                if not self.resource_controller.is_alive():
                    logger.error("Resource Controller died, restarting...")
                    self.resource_controller.start()
                
                if not self.connectivity_checker.is_alive():
                    logger.error("Connectivity Checker died, restarting...")
                    self.connectivity_checker.start()
                
                if not self.metrics_server.is_alive():
                    logger.error("Metrics Server died, restarting...")
                    self.metrics_server.start()
                
                if not self.api_server.is_alive():
                    logger.error("API Server died, restarting...")
                    self.api_server.start()
                    self.shared_state['api_server_running'] = True
                
                # Log status periodically
                cpu = self.shared_state.get('cpu_percent', 0)
                ram = self.shared_state.get('ram_percent', 0)
                throttle = self.shared_state.get('throttle_level', 0)
                aws_ready = self.shared_state.get('aws_ready', False)
                api_running = self.shared_state.get('api_server_running', False)
                
                logger.info(
                    f"Status - CPU: {cpu:.1f}%, RAM: {ram:.1f}%, "
                    f"Throttle: {throttle}, AWS: {aws_ready}, API: {api_running}"
                )
                
                # Sleep
                time.sleep(30)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.shutdown_event.set()
    
    def run(self) -> int:
        """
        Main execution flow
        
        Returns:
            Exit code (0 = success, 1 = failure)
        """
        try:
            # Verify Git branch
            if not self._verify_git_branch():
                logger.error("Git branch verification failed")
                return 1
            
            # Start child processes
            if not self._start_child_processes():
                logger.error("Failed to start child processes")
                return 1
            
            # Phase A: Verify AWS
            if not self._phase_a_verify_aws():
                logger.error("Phase A failed")
                self._stop_child_processes()
                return 1
            
            # Phase B: Generate configurations
            if not self._phase_b_generate_configs():
                logger.error("Phase B failed")
                self._stop_child_processes()
                return 1
            
            # Phase C: Start Docker stack
            if not self._phase_c_start_docker():
                logger.error("Phase C failed")
                self._stop_child_processes()
                return 1
            
            # Phase D: Wait for connectivity
            if not self._phase_d_wait_connectivity():
                logger.error("Phase D failed")
                self._stop_child_processes()
                return 1
            
            # Phase E: Verify pipeline
            if not self._phase_e_verify_pipeline():
                logger.error("Phase E failed")
                self._stop_child_processes()
                return 1
            
            # Phase F: Commit changes
            self._phase_f_commit_changes()
            
            # Phase G: Monitor
            self._phase_g_monitor()
            
            # Shutdown
            logger.info("Initiating graceful shutdown...")
            self._stop_child_processes()
            
            logger.info("IDS2 Agent stopped successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self._stop_child_processes()
            return 1


def main():
    """Main entry point"""
    # Check for config file argument
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    
    # Create and run agent
    agent = IDS2Agent(config_path)
    exit_code = agent.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
