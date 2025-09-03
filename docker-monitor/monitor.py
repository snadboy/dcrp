#!/usr/bin/env python3
"""
DCRP Docker Monitor Service
Monitors Docker containers via SSH and automatically creates/updates routes
"""

import os
import sys
import time
import json
import logging
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

from snadboy_ssh_docker import SSHDockerClient
from snadboy_ssh_docker.exceptions import SSHDockerError
import httpx
import yaml

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dcrp-docker-monitor")

# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://api-server:8000')
MONITOR_INTERVAL = int(os.environ.get('MONITOR_INTERVAL', '30'))
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config')

class DockerMonitor:
    def __init__(self):
        self.api_base_url = API_BASE_URL.rstrip('/')
        self.ssh_client = None
        self.http_client = None
        self.config = {}
        self.managed_routes = set()
        self.static_routes = {}  # Static routes from config
        self.running = False
        self.enabled_hosts = {}
        
    async def initialize(self):
        """Initialize the monitor service"""
        try:
            # Load configuration first
            await self.load_config()
            
            # Initialize SSH Docker client from config file (like docker-revp)
            hosts_config_file = os.path.join(CONFIG_PATH, 'hosts.yml')
            self.ssh_client = SSHDockerClient.from_config(hosts_config_file)
            
            # Get enabled hosts from SSH client configuration
            if hasattr(self.ssh_client, 'hosts_config') and self.ssh_client.hosts_config:
                hosts_config = self.ssh_client.hosts_config.hosts
                self.enabled_hosts = {
                    name: host_config for name, host_config in hosts_config.items()
                    if host_config.enabled
                }
            
            # Initialize HTTP client for API calls
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(max_connections=10)
            )
            
            logger.info(f"Docker Monitor initialized successfully with {len(self.enabled_hosts)} SSH hosts")
            
        except Exception as e:
            logger.error(f"Failed to initialize Docker Monitor: {e}")
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
            
            # Load static routes configuration
            static_routes_path = os.path.join(CONFIG_PATH, 'static-routes.yml')
            if os.path.exists(static_routes_path):
                with open(static_routes_path, 'r') as f:
                    static_config = yaml.safe_load(f) or {}
                    self.static_routes = static_config.get('static_routes', {})
                    logger.info(f"Loaded {len(self.static_routes)} static routes from config")
            else:
                self.static_routes = {}
                logger.info("No static routes configuration found")
            
            # SSH client will be initialized later with the config
            # We'll get enabled hosts from the SSH client after initialization
            self.enabled_hosts = {}
                
            logger.info("Loaded Docker monitor configuration")
            
        except Exception as e:
            logger.error(f"Failed to load Docker monitor configuration: {e}")
            self.config = {}
            self.static_routes = {}
            self.enabled_hosts = {}
    
    def _generate_ssh_alias(self, host_name: str, host_config) -> str:
        """Generate SSH alias for host (matching docker-revp format)"""
        hostname = host_config.hostname
        port = getattr(host_config, 'port', 22)
        return f"docker-{hostname.replace('.', '-').replace(':', '-')}-{port}"
    
    def _parse_revp_services(self, labels: dict) -> dict:
        """Parse port-based service configurations from docker-revp labels."""
        services = {}
        
        # DEBUG: Log all labels to see what we're working with
        logger.debug(f"DEBUG: Parsing labels: {labels}")
        
        revp_labels = {}
        for label_key, value in labels.items():
            if label_key.startswith("snadboy.revp."):
                revp_labels[label_key] = value
        
        logger.debug(f"DEBUG: Found revp labels: {revp_labels}")
        
        for label_key, value in labels.items():
            if not label_key.startswith("snadboy.revp."):
                continue
            
            logger.debug(f"DEBUG: Processing revp label: {label_key} = {value}")
            
            # Split label: snadboy.revp.{port}.{property}
            parts = label_key.split(".")
            if len(parts) != 4:
                logger.debug(f"DEBUG: Skipping label with wrong parts count: {len(parts)} parts")
                continue
            
            prefix, revp, port, property_name = parts
            
            # Validate port is numeric
            if not port.isdigit():
                logger.debug(f"DEBUG: Skipping non-numeric port: {port}")
                continue
            
            logger.debug(f"DEBUG: Valid revp label - port: {port}, property: {property_name}, value: {value}")
            
            # Initialize service if not exists
            if port not in services:
                services[port] = {}
            
            # Store property for this port
            services[port][property_name] = value
        
        logger.debug(f"DEBUG: Parsed services: {services}")
        
        # Filter services that have required 'domain' property
        valid_services = {}
        for port, service_labels in services.items():
            logger.debug(f"DEBUG: Checking service for port {port}: {service_labels}")
            if 'domain' in service_labels:
                valid_services[port] = {
                    'port': port,
                    'domain': service_labels['domain'],
                    'backend_proto': service_labels.get('backend-proto', 'http'),
                    'backend_path': service_labels.get('backend-path', '/'),
                }
                logger.debug(f"DEBUG: Valid service created for port {port}: {valid_services[port]}")
            else:
                logger.debug(f"DEBUG: Service for port {port} missing 'domain' property")
        
        logger.debug(f"DEBUG: Final valid services: {valid_services}")
        return valid_services

    async def scan_ssh_host_containers(self, host_name: str, host_config) -> List[Dict[str, Any]]:
        """Scan containers on an SSH host"""
        try:
            # Generate SSH alias like docker-revp does
            ssh_alias = self._generate_ssh_alias(host_name, host_config)
            logger.debug(f"DEBUG: Scanning host {host_name} using SSH alias: {ssh_alias}")
            
            # Try direct SSH approach first to debug
            import subprocess
            import json
            import asyncio
            
            # Get actual user from host_config
            ssh_user = getattr(host_config, "user", "revp")
            ssh_hostname = getattr(host_config, "hostname", "localhost")
            ssh_port = getattr(host_config, "port", 22)
            ssh_key = getattr(host_config, "key_file", "/home/monitor/.ssh/docker_monitor_key")
            
            # Build SSH command to get container data with labels
            ssh_cmd = [
                'ssh', 
                '-i', ssh_key,
                '-p', str(ssh_port),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'CanonicalizeHostname=no',
                '-o', 'ConnectTimeout=10',
                f'{ssh_user}@{ssh_hostname}',
                'docker', 'ps', '--format', 'json'
            ]
            
            logger.debug(f"DEBUG: Running SSH command: {' '.join(ssh_cmd)}")
            
            # Execute SSH command
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"SSH connection failed for host {host_name} ({ssh_user}@{ssh_hostname}:{ssh_port}): {error_msg}")
                
                # Report error to API for dashboard visibility
                await self.report_host_error(host_name, f"SSH connection failed: {error_msg}")
                return []
            
            # Parse JSON output - each line is a separate JSON object
            containers_data = []
            for line in stdout.decode().strip().split('\n'):
                if line.strip():
                    try:
                        container_json = json.loads(line)
                        containers_data.append(container_json)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse container JSON: {e}")
            
            logger.debug(f"DEBUG: Found {len(containers_data)} containers on {host_name} via direct SSH")
            containers = containers_data
            
            results = []
            for container_data in containers:
                # Extract container name for debugging - docker ps format uses "Names" key directly
                container_name = container_data.get('Names', 'unknown')
                logger.debug(f"DEBUG: Processing container: {container_name}")
                
                # Get labels from container data - docker ps format has labels as comma-separated string
                labels_str = container_data.get("Labels", "")
                labels = {}
                if isinstance(labels_str, str) and labels_str:
                    # Parse comma-separated labels into dictionary
                    for label_pair in labels_str.split(','):
                        if '=' in label_pair:
                            key, value = label_pair.split('=', 1)
                            labels[key] = value
                    logger.debug(f"DEBUG: Parsed {len(labels)} labels for container {container_name}")
                elif isinstance(labels_str, dict):
                    labels = labels_str
                    logger.debug(f"DEBUG: Container {container_name} already has dict labels")
                else:
                    logger.debug(f"DEBUG: Container {container_name} has no labels")
                    continue
                
                # Parse docker-revp format services
                logger.debug(f"DEBUG: Parsing services for container: {container_name}")
                services = self._parse_revp_services(labels)
                
                if not services:
                    # No valid services found
                    continue
                
                # Extract container info - docker ps format
                container_name = container_data.get('Names', 'unknown')
                container_id = container_data.get('ID', '')[:12]
                host_hostname = getattr(host_config, 'hostname', 'localhost')
                
                # Create a route for each service (port)
                for port, service_info in services.items():
                    upstream = f"{host_hostname}:{port}"
                    
                    results.append({
                        'route_id': f"monitor_{host_name}_{container_name}_{container_id}_{port}",
                        'host': service_info['domain'],
                        'upstream': upstream,
                        'container_name': container_name,
                        'container_id': container_id,
                        'container_port': port,
                        'ssh_host': host_name,
                        'protocol': service_info['backend_proto'],
                        'labels': labels
                    })
            
            logger.debug(f"Found {len(results)} monitored services across containers on {host_name}")
            
            # Report successful connection
            await self.report_host_success(host_name)
            
            return results
            
        except SSHDockerError as e:
            logger.error(f"SSH Docker error scanning {host_name}: {e}")
            await self.report_host_error(host_name, str(e))
            return []
        except Exception as e:
            logger.error(f"Failed to scan containers on {host_name}: {e}")
            await self.report_host_error(host_name, str(e))
            return []

    async def sync_all_ssh_hosts(self):
        """Synchronize containers from all enabled SSH hosts"""
        current_containers = {}
        
        for host_name, host_config in self.enabled_hosts.items():
            logger.debug(f"Scanning containers on SSH host: {host_name}")
            containers = await self.scan_ssh_host_containers(host_name, host_config)
            
            for container_info in containers:
                current_containers[container_info['route_id']] = container_info
        
        return current_containers

    async def check_api_health(self) -> bool:
        """Check if the API server is healthy"""
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            response.raise_for_status()
            data = response.json()
            return data.get('status') in ['healthy', 'ok']
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False
    
    async def create_route(self, container_info: Dict[str, Any]) -> bool:
        """Create a route for a container service"""
        try:
            # Split upstream into components
            upstream = container_info['upstream']  # format: "hostname:port"
            upstream_host, upstream_port_str = upstream.split(':', 1)
            upstream_port = int(upstream_port_str)
            
            route_data = {
                'host': container_info['host'],
                'upstream_protocol': container_info.get('protocol', 'http'),
                'upstream_host': upstream_host,
                'upstream_port': upstream_port,
                'route_id': container_info['route_id'],
                'source': 'monitor'
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/routes",
                json=route_data
            )
            
            if response.status_code == 200:
                self.managed_routes.add(container_info['route_id'])
                logger.info(f"Created route for container {container_info['container_name']} port {container_info['container_port']}: "
                           f"{container_info['host']} -> {container_info['upstream']}")
                return True
            else:
                logger.error(f"Failed to create route: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create route for {container_info['container_name']}: {e}")
            return False
    
    async def create_static_route(self, route_id: str, route_config: Dict[str, Any]) -> bool:
        """Create a static route from configuration"""
        try:
            route_data = {
                'host': route_config['host'],
                'upstream_protocol': route_config.get('upstream_protocol', 'http'),
                'upstream_host': route_config['upstream_host'],
                'upstream_port': route_config['upstream_port'],
                'route_id': f"static_{route_id}",
                'source': 'static'
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/routes",
                json=route_data
            )
            
            if response.status_code == 200:
                self.managed_routes.add(f"static_{route_id}")
                logger.info(f"Created static route {route_id}: {route_config['host']} -> {route_config['upstream']}")
                return True
            else:
                logger.error(f"Failed to create static route {route_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create static route {route_id}: {e}")
            return False
    
    async def apply_static_routes(self) -> None:
        """Apply all static routes from configuration"""
        if not self.static_routes:
            logger.info("No static routes to apply")
            return
            
        logger.info(f"Applying {len(self.static_routes)} static routes...")
        for route_id, route_config in self.static_routes.items():
            await self.create_static_route(route_id, route_config)

    async def delete_route(self, route_id: str) -> bool:
        """Delete a route"""
        try:
            response = await self.http_client.delete(f"{self.api_base_url}/routes/{route_id}")
            
            if response.status_code == 200:
                self.managed_routes.discard(route_id)
                logger.info(f"Deleted route: {route_id}")
                return True
            elif response.status_code == 404:
                # Route already doesn't exist
                self.managed_routes.discard(route_id)
                return True
            else:
                logger.error(f"Failed to delete route {route_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete route {route_id}: {e}")
            return False
    
    async def sync_containers(self):
        """Synchronize routes for all containers from SSH hosts"""
        try:
            if not self.enabled_hosts:
                logger.info("No enabled SSH hosts configured - Docker monitor will idle")
                return
            
            # Get existing monitored routes
            try:
                response = await self.http_client.get(f"{self.api_base_url}/routes")
                response.raise_for_status()
                existing_routes = {route['route_id'] for route in response.json() 
                                 if route['route_id'].startswith('monitor_')}
            except Exception as e:
                logger.error(f"Failed to get existing routes: {e}")
                existing_routes = set()
            
            # Collect all current containers from SSH hosts
            current_containers = await self.sync_all_ssh_hosts()
            
            logger.info(f"Found {len(current_containers)} services with docker-revp labels across {len(self.enabled_hosts)} SSH hosts")
            
            # Create routes for new containers
            for route_id, container_info in current_containers.items():
                if route_id not in existing_routes:
                    await self.create_route(container_info)
            
            # Remove routes for containers that no longer exist
            for route_id in existing_routes:
                if route_id not in current_containers:
                    await self.delete_route(route_id)
            
            logger.debug(f"Docker Monitor sync completed: {len(current_containers)} containers across {len(self.enabled_hosts)} hosts")
            
        except Exception as e:
            logger.error(f"Failed to sync SSH hosts: {e}")
    
    async def run(self):
        """Main monitoring loop"""
        self.running = True
        logger.info(f"Starting Docker Monitor with {MONITOR_INTERVAL}s interval")
        
        try:
            # Apply static routes on startup
            await self.apply_static_routes()
            
            while self.running:
                start_time = time.time()
                
                # Perform synchronization
                await self.sync_containers()
                
                # Calculate sleep time to maintain interval
                elapsed = time.time() - start_time
                sleep_time = max(0, MONITOR_INTERVAL - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        finally:
            self.running = False
            await self.cleanup()
    
    async def report_host_error(self, host_name: str, error_message: str):
        """Report host connection error to the API"""
        try:
            # Report error status to API
            status_data = {
                "status": "error",
                "message": error_message
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/hosts/{host_name}/status",
                json=status_data
            )
            
            if response.status_code == 200:
                logger.info(f"Reported error for host {host_name} to API")
            else:
                logger.warning(f"Failed to report host error (status {response.status_code})")
            
        except Exception as e:
            logger.error(f"Failed to report host error to API: {e}")
    
    async def report_host_success(self, host_name: str):
        """Report successful host connection to the API"""
        try:
            # Report success status to API
            status_data = {
                "status": "success",
                "message": "Connected successfully"
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/hosts/{host_name}/status",
                json=status_data
            )
            
            if response.status_code == 200:
                logger.debug(f"Reported success for host {host_name} to API")
            
        except Exception as e:
            logger.error(f"Failed to report host success to API: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Close HTTP client
            if self.http_client:
                await self.http_client.aclose()
                
            logger.info("Docker Monitor cleanup completed")
            
        except Exception as e:
            logger.error(f"Docker Monitor cleanup error: {e}")

async def main():
    """Main entry point"""
    logger.info("Docker Monitor main() function started")
    monitor = DockerMonitor()
    
    try:
        logger.info("Initializing Docker Monitor...")
        await monitor.initialize()
        logger.info("Starting Docker Monitor run loop...")
        await monitor.run()
        logger.info("Docker Monitor run loop completed")
    except Exception as e:
        logger.error(f"Docker Monitor failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Docker Monitor main() function exiting")

if __name__ == "__main__":
    asyncio.run(main())