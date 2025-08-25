#!/usr/bin/env python3
"""
DCRP SSH Manager Service
Manages SSH connections to remote Docker hosts for multi-host monitoring
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

import paramiko
import yaml
import httpx

# Configure logging with error capture
logging.basicConfig(
    level=logging.DEBUG,  # Force DEBUG level to catch everything
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Also log to stderr to ensure we see errors
logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logger = logging.getLogger("dcrp-ssh-manager")

# SANITY CHECK - This should always be visible
logger.error("SSH MANAGER STARTING - SANITY CHECK ERROR MESSAGE")
logger.info("SSH MANAGER STARTING - SANITY CHECK INFO MESSAGE")
print("DIRECT PRINT - SSH MANAGER STARTING")  # Direct print to stdout

# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://api-server:8000')
SSH_KEY_PATH = os.environ.get('SSH_KEY_PATH', '/app/ssh-keys/id_rsa')
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config')
CONNECTION_TIMEOUT = int(os.environ.get('SSH_CONNECTION_TIMEOUT', '30'))

class SSHManager:
    def __init__(self):
        self.api_base_url = API_BASE_URL.rstrip('/')
        self.http_client = None
        self.ssh_connections = {}
        self.config = {}
        self.running = False
        
    async def initialize(self):
        """Initialize the SSH manager service"""
        try:
            # Initialize HTTP client for API calls
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(max_connections=10)
            )
            
            # Load configuration
            await self.load_config()
            
            logger.info("SSH Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SSH Manager: {e}")
            raise
    
    async def load_config(self):
        """Load configuration from files"""
        try:
            # Load hosts configuration
            hosts_path = os.path.join(CONFIG_PATH, 'hosts.yml')
            if os.path.exists(hosts_path):
                with open(hosts_path, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                self.config = {}
                
            logger.info(f"Loaded SSH configuration from {hosts_path}")
            
        except Exception as e:
            logger.error(f"Failed to load SSH configuration: {e}")
            self.config = {}
    
    def create_ssh_client(self, host_config: Dict[str, Any]) -> Optional[paramiko.SSHClient]:
        """Create SSH client for a host"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load SSH key - try different key types
            ssh_key_path = host_config.get('ssh_key', SSH_KEY_PATH)
            if not os.path.exists(ssh_key_path):
                logger.error(f"SSH key not found: {ssh_key_path}")
                return None
            
            # Try different key types
            private_key = None
            key_types = [
                paramiko.Ed25519Key,
                paramiko.RSAKey,
                paramiko.ECDSAKey,
                paramiko.DSSKey
            ]
            
            for key_type in key_types:
                try:
                    private_key = key_type.from_private_key_file(ssh_key_path)
                    logger.info(f"Successfully loaded {key_type.__name__} from {ssh_key_path}")
                    break
                except Exception as e:
                    logger.info(f"Failed to load as {key_type.__name__}: {e}")
                    continue
            
            if private_key is None:
                logger.error(f"Could not load SSH key from {ssh_key_path} with any supported key type")
                return None
            
            # Connect
            client.connect(
                hostname=host_config['hostname'],
                port=host_config.get('port', 22),
                username=host_config['username'],
                pkey=private_key,
                timeout=CONNECTION_TIMEOUT,
                banner_timeout=30
            )
            
            logger.info(f"SSH connection established to {host_config['hostname']}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create SSH connection to {host_config.get('hostname')}: {e}")
            return None
    
    async def execute_command(self, host_name: str, command: str) -> Optional[str]:
        """Execute command on remote host via SSH"""
        try:
            host_config = self.config.get('hosts', {}).get(host_name)
            if not host_config or host_config.get('type') != 'ssh':
                return None
            
            # Get or create SSH connection
            if host_name not in self.ssh_connections:
                client = self.create_ssh_client(host_config)
                if not client:
                    return None
                self.ssh_connections[host_name] = client
            
            client = self.ssh_connections[host_name]
            
            # Execute command
            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            
            # Get results
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                logger.warning(f"SSH command error on {host_name}: {error}")
            
            return output
            
        except Exception as e:
            logger.error(f"Failed to execute SSH command on {host_name}: {e}")
            # Remove failed connection
            if host_name in self.ssh_connections:
                try:
                    self.ssh_connections[host_name].close()
                except:
                    pass
                del self.ssh_connections[host_name]
            return None
    
    async def get_remote_containers(self, host_name: str) -> List[Dict[str, Any]]:
        """Get Docker containers from remote host"""
        try:
            # Use docker command to list containers with labels
            command = 'docker ps --format "{{json .}}" --filter "label=dcrp.enable=true"'
            output = await self.execute_command(host_name, command)
            
            if not output:
                return []
            
            containers = []
            for line in output.split('\n'):
                if line.strip():
                    try:
                        import json
                        container_data = json.loads(line)
                        
                        # Get detailed container info including labels
                        container_id = container_data.get('ID', '')
                        if container_id:
                            inspect_cmd = f'docker inspect {container_id}'
                            inspect_output = await self.execute_command(host_name, inspect_cmd)
                            
                            if inspect_output:
                                container_details = json.loads(inspect_output)[0]
                                containers.append({
                                    'host_name': host_name,
                                    'container_data': container_data,
                                    'container_details': container_details
                                })
                                
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse container JSON: {e}")
                        continue
            
            return containers
            
        except Exception as e:
            logger.error(f"Failed to get containers from {host_name}: {e}")
            return []
    
    def extract_container_route_info(self, container_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract route information from remote container"""
        try:
            host_name = container_info['host_name']
            container_details = container_info['container_details']
            container_data = container_info['container_data']
            
            labels = container_details.get('Config', {}).get('Labels', {}) or {}
            
            # Check if container should be monitored
            if not labels.get('dcrp.enable', '').lower() == 'true':
                return None
            
            host = labels.get('dcrp.host')
            port = labels.get('dcrp.port')
            
            if not host or not port:
                return None
            
            container_name = container_details.get('Name', '').lstrip('/')
            container_id = container_details.get('Id', '')[:12]
            
            # For remote containers, use the SSH host's IP/hostname
            host_config = self.config.get('hosts', {}).get(host_name, {})
            remote_host = host_config.get('hostname', 'localhost')
            upstream = f"{remote_host}:{port}"
            
            # If the container exposes a different port, use that
            ports = container_details.get('NetworkSettings', {}).get('Ports', {})
            if f"{port}/tcp" in ports and ports[f"{port}/tcp"]:
                host_port = ports[f"{port}/tcp"][0]['HostPort']
                upstream = f"{remote_host}:{host_port}"
            
            return {
                'route_id': f"ssh_{host_name}_{container_name}_{container_id}",
                'host': host,
                'upstream': upstream,
                'force_ssl': labels.get('dcrp.ssl', '').lower() == 'true',
                'websocket': labels.get('dcrp.websocket', '').lower() == 'true',
                'container_name': container_name,
                'container_id': container_id,
                'remote_host': host_name,
                'labels': labels
            }
            
        except Exception as e:
            logger.error(f"Failed to extract container route info: {e}")
            return None
    
    async def create_route(self, container_info: Dict[str, Any]) -> bool:
        """Create a route for a remote container"""
        try:
            route_data = {
                'host': container_info['host'],
                'upstream': container_info['upstream'],
                'route_id': container_info['route_id'],
                'force_ssl': container_info['force_ssl'],
                'websocket': container_info['websocket']
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/routes",
                json=route_data
            )
            
            if response.status_code == 200:
                logger.info(f"Created SSH route for {container_info['remote_host']}:"
                           f"{container_info['container_name']}: "
                           f"{container_info['host']} -> {container_info['upstream']}")
                return True
            else:
                logger.error(f"Failed to create SSH route: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create SSH route: {e}")
            return False
    
    async def delete_route(self, route_id: str) -> bool:
        """Delete a route"""
        try:
            response = await self.http_client.delete(f"{self.api_base_url}/routes/{route_id}")
            
            if response.status_code == 200:
                logger.info(f"Deleted SSH route: {route_id}")
                return True
            elif response.status_code == 404:
                # Route already doesn't exist
                return True
            else:
                logger.error(f"Failed to delete SSH route {route_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete SSH route {route_id}: {e}")
            return False
    
    async def sync_ssh_hosts(self):
        """Synchronize routes for all SSH hosts (including localhost)"""
        try:
            hosts_config = self.config.get('hosts', {})
            ssh_hosts = {name: config for name, config in hosts_config.items() 
                        if config.get('type') == 'ssh' and config.get('enabled', False)}
            
            if not ssh_hosts:
                logger.info("No enabled SSH hosts configured - SSH manager will idle")
                return
            
            # Get existing SSH routes
            try:
                response = await self.http_client.get(f"{self.api_base_url}/routes")
                response.raise_for_status()
                existing_routes = {route['route_id'] for route in response.json() 
                                 if route['route_id'].startswith('ssh_')}
            except Exception as e:
                logger.error(f"Failed to get existing SSH routes: {e}")
                existing_routes = set()
            
            # Collect all current containers from SSH hosts
            current_containers = {}
            
            for host_name in ssh_hosts:
                containers = await self.get_remote_containers(host_name)
                for container_info in containers:
                    route_info = self.extract_container_route_info(container_info)
                    if route_info:
                        current_containers[route_info['route_id']] = route_info
            
            # Create routes for new containers
            for route_id, container_info in current_containers.items():
                if route_id not in existing_routes:
                    await self.create_route(container_info)
            
            # Remove routes for containers that no longer exist
            for route_id in existing_routes:
                if route_id not in current_containers:
                    await self.delete_route(route_id)
            
            logger.debug(f"SSH sync completed: {len(current_containers)} containers across {len(ssh_hosts)} hosts")
            
        except Exception as e:
            logger.error(f"Failed to sync SSH hosts: {e}")
    
    async def run(self):
        """Main SSH manager loop"""
        self.running = True
        logger.info("Starting SSH Manager")
        
        try:
            while self.running:
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    # Perform synchronization
                    logger.info("Starting SSH host synchronization cycle")
                    await self.sync_ssh_hosts()
                    logger.info("SSH host synchronization cycle completed")
                    
                    # Sleep for 60 seconds between syncs
                    elapsed = asyncio.get_event_loop().time() - start_time
                    sleep_time = max(0, 60 - elapsed)
                    
                    if sleep_time > 0:
                        logger.info(f"Sleeping for {sleep_time:.1f} seconds until next sync")
                        await asyncio.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Error in SSH Manager sync cycle: {e}", exc_info=True)
                    # Sleep a bit before retrying
                    await asyncio.sleep(10)
                    
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"SSH Manager loop error: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("SSH Manager stopping, cleaning up...")
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Close SSH connections
            for host_name, client in self.ssh_connections.items():
                try:
                    client.close()
                    logger.info(f"Closed SSH connection to {host_name}")
                except:
                    pass
            
            # Close HTTP client
            if self.http_client:
                await self.http_client.aclose()
                
            logger.info("SSH Manager cleanup completed")
            
        except Exception as e:
            logger.error(f"SSH Manager cleanup error: {e}")

async def main():
    """Main entry point"""
    logger.info("SSH Manager main() function started")
    manager = SSHManager()
    
    try:
        logger.info("Initializing SSH Manager...")
        await manager.initialize()
        logger.info("Starting SSH Manager run loop...")
        await manager.run()
        logger.info("SSH Manager run loop completed")
    except Exception as e:
        logger.error(f"SSH Manager failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("SSH Manager main() function exiting")

if __name__ == "__main__":
    logger.info("Starting asyncio event loop...")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to run asyncio loop: {e}", exc_info=True)
        sys.exit(1)
    logger.info("Asyncio event loop completed")