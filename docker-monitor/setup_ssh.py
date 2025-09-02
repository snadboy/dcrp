#!/usr/bin/env python3
"""
SSH setup script for docker-monitor container.
Configures SSH environment for snadboy-ssh-docker library.
"""

import os
import stat
import shutil
from pathlib import Path

def setup_ssh_environment():
    """Set up SSH configuration for container monitoring."""
    
    # Paths
    ssh_dir = Path("/home/monitor/.ssh")
    config_dir = Path("/app/config")
    ssh_keys_dir = Path("/app/ssh-keys")
    
    # Ensure SSH directory exists
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    
    print(f"Setting up SSH environment in {ssh_dir}")
    
    # Copy SSH key to home directory with correct name and permissions
    source_key = ssh_keys_dir / "docker_monitor_key"
    dest_key = ssh_dir / "docker_monitor_key"
    
    if source_key.exists():
        print(f"Copying SSH key from {source_key} to {dest_key}")
        shutil.copy2(source_key, dest_key)
        # Set correct permissions (600)
        dest_key.chmod(stat.S_IRUSR | stat.S_IWUSR)
        print(f"Set SSH key permissions to 600")
    else:
        print(f"WARNING: SSH key not found at {source_key}")
    
    # Create SSH config file
    ssh_config = ssh_dir / "config"
    config_content = """# SSH configuration for docker-monitor
# Generated automatically

Host localhost
    HostName localhost
    User revp
    Port 22
    IdentityFile /home/monitor/.ssh/docker_monitor_key
    PasswordAuthentication no
    StrictHostKeyChecking accept-new
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ControlMaster auto
    ControlPath /home/monitor/.ssh/control-%r@%h:%p
    ControlPersist 10m

Host docker-localhost-22
    HostName localhost
    User revp
    Port 22
    IdentityFile /home/monitor/.ssh/docker_monitor_key
    PasswordAuthentication no
    StrictHostKeyChecking accept-new
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ControlMaster auto
    ControlPath /home/monitor/.ssh/control-%r@%h:%p
    ControlPersist 10m
"""
    
    print(f"Creating SSH config at {ssh_config}")
    ssh_config.write_text(config_content)
    ssh_config.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    
    print("SSH environment setup completed")
    return True

if __name__ == "__main__":
    try:
        setup_ssh_environment()
        print("SSH setup successful")
    except Exception as e:
        print(f"SSH setup failed: {e}")
        raise