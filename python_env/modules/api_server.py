"""
API Server Module (Process #5)

Exposes a Flask API for managing the IDS2 SOC Pipeline.
Provides endpoints for status, control, and configuration.

This runs as a separate process.
"""

import os
import logging
from multiprocessing import Process, Manager
from typing import Dict, Any

from flask import Flask, jsonify, request, render_template

logger = logging.getLogger(__name__)

import os
import logging
from multiprocessing import Process, Manager
from typing import Dict, Any

from flask import Flask, jsonify, request, render_template

# Import managers for service control
from modules.docker_manager import DockerManager
from modules.suricata_manager import SuricataManager

logger = logging.getLogger(__name__)

class APIServer:
    """Flask API server for IDS2 SOC Pipeline"""

    def __init__(self, config_manager, shared_state: Dict[str, Any], docker_manager: DockerManager, suricata_manager: SuricataManager):
        """
        Initialize API server

        Args:
            config_manager: Configuration manager instance
            shared_state: Shared state dictionary from multiprocessing.Manager()
            docker_manager: DockerManager instance for controlling Docker services
            suricata_manager: SuricataManager instance for controlling Suricata
        """
        self.config = config_manager
        self.shared_state = shared_state
        self.docker_manager = docker_manager
        self.suricata_manager = suricata_manager
        self.app = Flask(__name__, template_folder='templates', static_folder='static')
        
        api_server_config = self.config.get_section('api_server')
        self.port = api_server_config.get('port', 5000)
        self.host = api_server_config.get('host', '0.0.0.0')

        self.process: Process = None

        self._setup_routes()

    def _setup_routes(self):
        """Set up Flask API routes"""

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            return jsonify(self.shared_state)

        @self.app.route('/api/control/start', methods=['POST'])
        def start_service():
            service_name = request.json.get('service')
            if not service_name:
                return jsonify({"status": "error", "message": "Service name not provided"}), 400

            success = False
            message = ""
            if service_name == "suricata":
                success = self.suricata_manager.start() # Assuming a start method for Suricata
                message = f"Attempting to start Suricata. Success: {success}"
            elif service_name in self.docker_manager.services:
                success = self.docker_manager.restart_service(service_name) # Restart for Docker services
                message = f"Attempting to start/restart Docker service {service_name}. Success: {success}"
            else:
                message = f"Unknown service: {service_name}"
                return jsonify({"status": "error", "message": message}), 400
            
            logger.info(f"Request to start service: {service_name}. Result: {message}")
            return jsonify({"status": "success" if success else "error", "message": message})

        @self.app.route('/api/control/stop', methods=['POST'])
        def stop_service():
            service_name = request.json.get('service')
            if not service_name:
                return jsonify({"status": "error", "message": "Service name not provided"}), 400

            success = False
            message = ""
            if service_name == "suricata":
                success = self.suricata_manager.stop() # Assuming a stop method for Suricata
                message = f"Attempting to stop Suricata. Success: {success}"
            elif service_name in self.docker_manager.services:
                success = self.docker_manager.stop_service(service_name) # Stop for Docker services
                message = f"Attempting to stop Docker service {service_name}. Success: {success}"
            else:
                message = f"Unknown service: {service_name}"
                return jsonify({"status": "error", "message": message}), 400
            
            logger.info(f"Request to stop service: {service_name}. Result: {message}")
            return jsonify({"status": "success" if success else "error", "message": message})

        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            return jsonify(self.config.config)

        @self.app.route('/api/config/update', methods=['POST'])
        def update_config():
            new_config = request.json
            # Logic to update config.yaml (requires careful validation and reload)
            logger.info(f"Request to update config: {new_config}")
            return jsonify({"status": "success", "message": "Config update initiated"})

    def _run_flask_app(self):
        """Run the Flask application"""
        logger.info(f"Flask API server starting on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False)

    def start(self) -> None:
        """Start API server process"""
        if self.process and self.process.is_alive():
            logger.warning("API server already running")
            return

        self.process = Process(
            target=self._run_flask_app,
            name="APIServer"
        )
        self.process.start()
        logger.info(f"API server started (PID: {self.process.pid})")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop API server process

        Args:
            timeout: Maximum time to wait for process to stop
        """
        if not self.process or not self.process.is_alive():
            logger.warning("API server not running")
            return

        logger.info("Stopping API server...")
        self.process.terminate()
        self.process.join(timeout=timeout)

        if self.process.is_alive():
            logger.warning("API server did not stop gracefully, killing...")
            self.process.kill()
            self.process.join()

        logger.info("API server stopped")

    def is_alive(self) -> bool:
        """Check if API server process is alive"""
        return self.process and self.process.is_alive()
