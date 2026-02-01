"""
IDS2 SOC Pipeline - Multi-Process Agent Modules

This package contains all modules for the multi-process orchestration agent.
Each module is designed to be process-safe and resource-aware.
"""

__version__ = "1.0.0"
__author__ = "IDS2 SOC Team"

# Module exports
__all__ = [
    "config_manager",
    "resource_controller",
    "connectivity_async",
    "metrics_server",
    "aws_manager",
    "docker_manager",
    "vector_manager",
    "suricata_manager",
    "git_workflow",
]
