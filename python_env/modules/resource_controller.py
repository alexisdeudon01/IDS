"""
Resource Controller Module (Process #2)

Continuously monitors CPU and RAM usage, enforces limits,
and implements throttling strategy to stay within constraints.

This runs as a separate process and updates shared state.
"""

import os
import gc
import time
import psutil
import logging
from typing import Dict, Any
from multiprocessing import Process, Manager

logger = logging.getLogger(__name__)


class ResourceController:
    """Monitors and controls system resource usage"""
    
    # Throttling levels
    THROTTLE_NONE = 0      # < 50% usage
    THROTTLE_LIGHT = 1     # 50-60% usage
    THROTTLE_MEDIUM = 2    # 60-70% usage
    THROTTLE_HEAVY = 3     # > 70% usage
    
    def __init__(self, config_manager, shared_state: Dict[str, Any]):
        """
        Initialize resource controller
        
        Args:
            config_manager: Configuration manager instance
            shared_state: Shared state dictionary from multiprocessing.Manager()
        """
        self.config = config_manager
        self.shared_state = shared_state
        self.limits = config_manager.get_resource_limits()
        
        # Monitoring interval
        self.check_interval = 2.0  # seconds
        
        # Process reference
        self.process: Process = None
        
        # Initialize shared state
        self.shared_state['cpu_percent'] = 0.0
        self.shared_state['ram_percent'] = 0.0
        self.shared_state['throttle_level'] = self.THROTTLE_NONE
        self.shared_state['resource_ok'] = True
        self.shared_state['last_gc_time'] = time.time()
    
    def _get_cpu_usage(self) -> float:
        """
        Get current CPU usage percentage
        
        Returns:
            CPU usage as percentage (0-100)
        """
        # Get CPU usage over 1 second interval
        return psutil.cpu_percent(interval=1.0)
    
    def _get_ram_usage(self) -> float:
        """
        Get current RAM usage percentage
        
        Returns:
            RAM usage as percentage (0-100)
        """
        mem = psutil.virtual_memory()
        return mem.percent
    
    def _calculate_throttle_level(self, cpu: float, ram: float) -> int:
        """
        Calculate throttling level based on resource usage
        
        Args:
            cpu: CPU usage percentage
            ram: RAM usage percentage
            
        Returns:
            Throttle level (0-3)
        """
        max_usage = max(cpu, ram)
        
        if max_usage >= self.limits['throttle_threshold_3']:
            return self.THROTTLE_HEAVY
        elif max_usage >= self.limits['throttle_threshold_2']:
            return self.THROTTLE_MEDIUM
        elif max_usage >= self.limits['throttle_threshold_1']:
            return self.THROTTLE_LIGHT
        else:
            return self.THROTTLE_NONE
    
    def _should_force_gc(self, ram: float) -> bool:
        """
        Determine if garbage collection should be forced
        
        Args:
            ram: Current RAM usage percentage
            
        Returns:
            True if GC should be forced
        """
        # Force GC if RAM > 65% and hasn't been done in last 30 seconds
        last_gc = self.shared_state.get('last_gc_time', 0)
        time_since_gc = time.time() - last_gc
        
        return ram > 65.0 and time_since_gc > 30.0
    
    def _monitor_loop(self) -> None:
        """
        Main monitoring loop (runs in separate process)
        
        Continuously monitors resources and updates shared state.
        This is the entry point for Process #2.
        """
        logger.info("Resource controller process started")
        
        try:
            while True:
                # Get current usage
                cpu = self._get_cpu_usage()
                ram = self._get_ram_usage()
                
                # Calculate throttle level
                throttle = self._calculate_throttle_level(cpu, ram)
                
                # Check if limits exceeded
                resource_ok = (
                    cpu <= self.limits['max_cpu_percent'] and
                    ram <= self.limits['max_ram_percent']
                )
                
                # Update shared state
                self.shared_state['cpu_percent'] = cpu
                self.shared_state['ram_percent'] = ram
                self.shared_state['throttle_level'] = throttle
                self.shared_state['resource_ok'] = resource_ok
                
                # Log status
                if throttle > self.THROTTLE_NONE:
                    logger.warning(
                        f"Resource pressure detected - "
                        f"CPU: {cpu:.1f}%, RAM: {ram:.1f}%, "
                        f"Throttle level: {throttle}"
                    )
                else:
                    logger.debug(f"Resources OK - CPU: {cpu:.1f}%, RAM: {ram:.1f}%")
                
                # Force garbage collection if needed
                if self._should_force_gc(ram):
                    logger.info("Forcing garbage collection due to high RAM usage")
                    gc.collect()
                    self.shared_state['last_gc_time'] = time.time()
                
                # Alert if limits exceeded
                if not resource_ok:
                    logger.error(
                        f"RESOURCE LIMITS EXCEEDED! "
                        f"CPU: {cpu:.1f}% (limit: {self.limits['max_cpu_percent']}%), "
                        f"RAM: {ram:.1f}% (limit: {self.limits['max_ram_percent']}%)"
                    )
                
                # Sleep before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Resource controller received shutdown signal")
        except Exception as e:
            logger.error(f"Resource controller error: {e}", exc_info=True)
            self.shared_state['resource_ok'] = False
    
    def start(self) -> None:
        """Start resource monitoring process"""
        if self.process and self.process.is_alive():
            logger.warning("Resource controller already running")
            return
        
        self.process = Process(
            target=self._monitor_loop,
            name="ResourceController"
        )
        self.process.start()
        logger.info(f"Resource controller started (PID: {self.process.pid})")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop resource monitoring process
        
        Args:
            timeout: Maximum time to wait for process to stop
        """
        if not self.process or not self.process.is_alive():
            logger.warning("Resource controller not running")
            return
        
        logger.info("Stopping resource controller...")
        self.process.terminate()
        self.process.join(timeout=timeout)
        
        if self.process.is_alive():
            logger.warning("Resource controller did not stop gracefully, killing...")
            self.process.kill()
            self.process.join()
        
        logger.info("Resource controller stopped")
    
    def is_alive(self) -> bool:
        """Check if resource controller process is alive"""
        return self.process and self.process.is_alive()
    
    @staticmethod
    def get_throttle_params(throttle_level: int) -> Dict[str, Any]:
        """
        Get throttling parameters based on level
        
        Args:
            throttle_level: Current throttle level (0-3)
            
        Returns:
            Dictionary with throttling parameters
        """
        if throttle_level == ResourceController.THROTTLE_HEAVY:
            return {
                'sleep_multiplier': 4.0,
                'batch_size_divisor': 4,
                'pause_non_critical': True,
                'description': 'HEAVY throttling - critical only'
            }
        elif throttle_level == ResourceController.THROTTLE_MEDIUM:
            return {
                'sleep_multiplier': 2.0,
                'batch_size_divisor': 2,
                'pause_non_critical': False,
                'description': 'MEDIUM throttling - reduced load'
            }
        elif throttle_level == ResourceController.THROTTLE_LIGHT:
            return {
                'sleep_multiplier': 1.5,
                'batch_size_divisor': 1,
                'pause_non_critical': False,
                'description': 'LIGHT throttling - slight reduction'
            }
        else:
            return {
                'sleep_multiplier': 1.0,
                'batch_size_divisor': 1,
                'pause_non_critical': False,
                'description': 'NO throttling - full speed'
            }
