"""
Git Workflow Module

Handles Git operations for the IDS2 project.
Ensures work is done on 'dev' branch and commits/pushes changes.
"""

import os
import logging
import subprocess
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class GitWorkflow:
    """Manages Git workflow operations"""
    
    def __init__(self, config_manager):
        """
        Initialize Git workflow manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.git_config = config_manager.get_git_config()
        
        # Required branch
        self.required_branch = self.git_config.get('required_branch', 'dev')
        
        # Repository root
        self.repo_root = Path.cwd()
    
    def _run_git_command(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run git command
        
        Args:
            args: Git command arguments
            check: Whether to raise exception on non-zero exit
            
        Returns:
            CompletedProcess result
        """
        cmd = ['git'] + args
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=check
            )
            
            if result.stdout:
                logger.debug(f"stdout: {result.stdout.strip()}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr.strip()}")
            
            return result
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get current Git branch name
        
        Returns:
            Branch name or None if failed
        """
        try:
            result = self._run_git_command(['branch', '--show-current'])
            branch = result.stdout.strip()
            return branch if branch else None
        except Exception as e:
            logger.error(f"Failed to get current branch: {e}")
            return None
    
    def verify_on_required_branch(self) -> bool:
        """
        Verify that we're on the required branch
        
        Returns:
            True if on required branch
        """
        current_branch = self.get_current_branch()
        
        if current_branch is None:
            logger.error("Could not determine current branch")
            return False
        
        if current_branch != self.required_branch:
            logger.error(
                f"Not on required branch '{self.required_branch}' "
                f"(current: '{current_branch}')"
            )
            return False
        
        logger.info(f"On required branch: {self.required_branch}")
        return True
    
    def checkout_branch(self, branch: str, create: bool = False) -> bool:
        """
        Checkout a Git branch
        
        Args:
            branch: Branch name to checkout
            create: Whether to create the branch if it doesn't exist
            
        Returns:
            True if successful
        """
        try:
            args = ['checkout']
            if create:
                args.append('-b')
            args.append(branch)
            
            self._run_git_command(args)
            logger.info(f"Checked out branch: {branch}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to checkout branch {branch}: {e}")
            return False
    
    def get_status(self) -> Optional[str]:
        """
        Get Git status
        
        Returns:
            Status output or None
        """
        try:
            result = self._run_git_command(['status', '--short'])
            return result.stdout
        except Exception as e:
            logger.error(f"Failed to get Git status: {e}")
            return None
    
    def has_changes(self) -> bool:
        """
        Check if there are uncommitted changes
        
        Returns:
            True if there are changes
        """
        status = self.get_status()
        return bool(status and status.strip())
    
    def add_all(self) -> bool:
        """
        Stage all changes (git add -A)
        
        Returns:
            True if successful
        """
        try:
            self._run_git_command(['add', '-A'])
            logger.info("Staged all changes")
            return True
        except Exception as e:
            logger.error(f"Failed to stage changes: {e}")
            return False
    
    def commit(self, message: str) -> bool:
        """
        Commit staged changes
        
        Args:
            message: Commit message
            
        Returns:
            True if successful
        """
        try:
            self._run_git_command(['commit', '-m', message])
            logger.info(f"Committed changes: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to commit: {e}")
            return False
    
    def push(self, remote: str = 'origin', branch: Optional[str] = None) -> bool:
        """
        Push commits to remote
        
        Args:
            remote: Remote name (default: origin)
            branch: Branch name (default: current branch)
            
        Returns:
            True if successful
        """
        try:
            if branch is None:
                branch = self.get_current_branch()
            
            if branch is None:
                logger.error("Could not determine branch to push")
                return False
            
            self._run_git_command(['push', remote, branch])
            logger.info(f"Pushed to {remote}/{branch}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push: {e}")
            return False
    
    def commit_and_push(self, message: str) -> bool:
        """
        Stage all changes, commit, and push
        
        Args:
            message: Commit message
            
        Returns:
            True if successful
        """
        # Check if on required branch
        if not self.verify_on_required_branch():
            logger.error("Cannot commit: not on required branch")
            return False
        
        # Check if there are changes
        if not self.has_changes():
            logger.info("No changes to commit")
            return True
        
        # Stage changes
        if not self.add_all():
            return False
        
        # Commit
        if not self.commit(message):
            return False
        
        # Push
        if not self.push():
            return False
        
        logger.info("Successfully committed and pushed changes")
        return True
    
    def pull(self, remote: str = 'origin', branch: Optional[str] = None) -> bool:
        """
        Pull changes from remote
        
        Args:
            remote: Remote name (default: origin)
            branch: Branch name (default: current branch)
            
        Returns:
            True if successful
        """
        try:
            if branch is None:
                branch = self.get_current_branch()
            
            if branch is None:
                logger.error("Could not determine branch to pull")
                return False
            
            self._run_git_command(['pull', remote, branch])
            logger.info(f"Pulled from {remote}/{branch}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pull: {e}")
            return False
    
    def get_last_commit_hash(self) -> Optional[str]:
        """
        Get hash of last commit
        
        Returns:
            Commit hash or None
        """
        try:
            result = self._run_git_command(['rev-parse', 'HEAD'])
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Failed to get commit hash: {e}")
            return None
    
    def get_remote_url(self, remote: str = 'origin') -> Optional[str]:
        """
        Get URL of remote repository
        
        Args:
            remote: Remote name
            
        Returns:
            Remote URL or None
        """
        try:
            result = self._run_git_command(['remote', 'get-url', remote])
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Failed to get remote URL: {e}")
            return None
