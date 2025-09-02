#!/usr/bin/env python3
"""
DCRP API Server - FastAPI service for managing Caddy routes
Handles route CRUD operations, health checks, and configuration management
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple
import logging
from contextlib import asynccontextmanager
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, computed_field
import httpx
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dcrp-api")

# Configuration
CADDY_ADMIN_URL = os.environ.get('CADDY_ADMIN_URL', 'http://caddy:2019')
DEFAULT_SERVER = os.environ.get('CADDY_SERVER', 'srv0')
API_PORT = int(os.environ.get('API_PORT', '8000'))
API_HOST = os.environ.get('API_HOST', '0.0.0.0')
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config')
DNS_RESOLVER = os.environ.get('DNS_RESOLVER', '192.168.86.76:53')

class Config:
    caddy_admin_url = CADDY_ADMIN_URL
    default_server = DEFAULT_SERVER
    timeout = 10.0
    config_path = CONFIG_PATH
    dns_resolver = DNS_RESOLVER

config = Config()

# HTTP client for Caddy Admin API
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - setup and teardown"""
    global http_client
    
    # Startup
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(config.timeout),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
    )
    logger.info(f"DCRP API Server starting - Caddy Admin: {config.caddy_admin_url}")
    
    # Load and apply static routes from config file
    await load_and_apply_static_routes()
    
    yield
    
    # Shutdown
    if http_client:
        await http_client.aclose()
    logger.info("DCRP API Server shutting down")

# FastAPI app with lifespan management
app = FastAPI(
    title="DCRP API Server",
    description="Docker Container Reverse Proxy - Route Management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware for web UI integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class RouteCreate(BaseModel):
    host: str = Field(..., description="Domain/subdomain for the route")
    upstream_protocol: str = Field("http", description="Backend protocol: 'http' or 'https'")
    upstream_host: str = Field(..., description="Backend hostname or IP address")
    upstream_port: int = Field(..., description="Backend port number", ge=1, le=65535)
    route_id: Optional[str] = Field(None, description="Optional route identifier")
    source: str = Field("static", description="Route source type: 'static' or 'monitor'")
    
    # Backward compatibility property
    @property
    def upstream(self) -> str:
        return f"{self.upstream_host}:{self.upstream_port}"
    
    @property 
    def protocol(self) -> str:
        return self.upstream_protocol

class RouteUpdate(BaseModel):
    upstream_protocol: Optional[str] = Field(None, description="Backend protocol: 'http' or 'https'")
    upstream_host: Optional[str] = Field(None, description="Backend hostname or IP address")
    upstream_port: Optional[int] = Field(None, description="Backend port number", ge=1, le=65535)
    
    # Backward compatibility properties
    @property
    def upstream(self) -> Optional[str]:
        if self.upstream_host and self.upstream_port:
            return f"{self.upstream_host}:{self.upstream_port}"
        return None
    
    @property
    def protocol(self) -> Optional[str]:
        return self.upstream_protocol

class RouteResponse(BaseModel):
    route_id: str
    host: str
    upstream_protocol: str = "http"
    upstream_host: str
    upstream_port: int
    index: int
    terminal: bool = False
    source: str = "static"
    dns_resolver: Optional[str] = None
    
    # Backward compatibility fields (included in serialization)
    @computed_field
    @property
    def upstream(self) -> str:
        return f"{self.upstream_host}:{self.upstream_port}"
    
    @computed_field
    @property 
    def protocol(self) -> str:
        return self.upstream_protocol

class HealthResponse(BaseModel):
    status: str
    caddy_admin_url: str
    server: str
    version: str = "1.0.0"
    dns_resolver: str

# Host management models
class HostCreate(BaseModel):
    host_id: str = Field(..., description="Unique identifier for the host")
    hostname: str = Field(..., description="IP address or hostname for SSH connection")
    user: str = Field("revp", description="SSH username")
    port: int = Field(22, description="SSH port number")
    key_file: str = Field("/app/ssh-keys/docker_monitor_key", description="Path to SSH private key")
    description: Optional[str] = Field(None, description="Host description")
    enabled: bool = Field(True, description="Whether monitoring is enabled")

class HostUpdate(BaseModel):
    hostname: Optional[str] = Field(None, description="IP address or hostname for SSH connection")
    user: Optional[str] = Field(None, description="SSH username")
    port: Optional[int] = Field(None, description="SSH port number")
    key_file: Optional[str] = Field(None, description="Path to SSH private key")
    description: Optional[str] = Field(None, description="Host description")
    enabled: Optional[bool] = Field(None, description="Whether monitoring is enabled")

class HostResponse(BaseModel):
    host_id: str
    hostname: str
    user: str
    port: int
    key_file: str
    description: Optional[str] = None
    enabled: bool
    last_seen: Optional[str] = None
    status: str = "unknown"

# Helper functions
async def get_caddy_client() -> httpx.AsyncClient:
    """Get HTTP client for Caddy Admin API"""
    if not http_client:
        raise HTTPException(status_code=500, detail="HTTP client not initialized")
    return http_client

def server_routes_path(server: str) -> str:
    """Get API path for server routes"""
    return f"/config/apps/http/servers/{server}/routes"

def build_enhanced_reverse_proxy_handler(upstream_host: str, upstream_port: int, route_id: str, upstream_protocol: str = "http") -> Dict[str, Any]:
    """Build enhanced reverse proxy handler with debugging headers and DNS resolver"""
    # Construct upstream address from components
    upstream = f"{upstream_host}:{upstream_port}"
    # For HTTPS backends, we need to update the upstream dial to use https:// scheme
    upstream_dial = f"{upstream_protocol}://{upstream}" if upstream_protocol == "https" else upstream
    
    handler = {
        "handler": "reverse_proxy",
        "upstreams": [{"dial": upstream_dial}],
        # Add transport configuration with custom DNS resolver
        # Note: transport protocol is always "http" in Caddy - HTTPS is handled by upstream URL scheme
        "transport": {
            "protocol": "http",
            "resolver": {
                "addresses": [config.dns_resolver]
            }
        },
        # Add debugging headers
        "headers": {
            "request": {
                "set": {
                    "X-DCRP-Route-ID": [route_id],
                    "X-DCRP-Upstream": [upstream],
                    "X-Forwarded-Host": ["{http.request.host}"],
                    "X-Forwarded-For": ["{http.request.remote_host}"],
                    "X-Forwarded-Proto": ["{http.request.scheme}"],
                    "X-Real-IP": ["{http.request.remote_host}"]
                }
            },
            "response": {
                "set": {
                    "X-DCRP-Route-ID": [route_id],
                    "X-DCRP-Backend": [upstream]
                }
            }
        }
    }
    
    # For HTTPS backends, add TLS configuration to handle self-signed certificates
    if upstream_protocol == "https":
        handler["transport"]["tls"] = {
            "insecure_skip_verify": True
        }
    
    return handler

def build_reverse_proxy_route(
    host: str, 
    upstream_host: str,
    upstream_port: int,
    route_id: str,
    upstream_protocol: str = "http"
) -> Dict[str, Any]:
    """Build a Caddy reverse proxy route configuration with automatic HTTPS"""
    
    # Always use HTTPS with HTTP->HTTPS redirect (since we have wildcard certificate)
    route = {
        "@id": route_id,
        "match": [{"host": [host]}],
        "handle": [{
            "handler": "subroute",
            "routes": [
                {
                    "match": [{"protocol": "http"}],
                    "handle": [{
                        "handler": "static_response",
                        "headers": {
                            "Location": [f"https://{host}{{http.request.uri}}"]
                        },
                        "status_code": 308
                    }]
                },
                {
                    "match": [{"protocol": "https"}],
                    "handle": [build_enhanced_reverse_proxy_handler(upstream_host, upstream_port, route_id, upstream_protocol)]
                }
            ]
        }]
    }
    
    return route

def extract_route_info(route: Dict[str, Any]) -> Dict[str, Any]:
    """Extract route information for API responses"""
    # Get host
    hosts = []
    if route.get("match"):
        for match in route["match"]:
            if "host" in match:
                hosts.extend(match["host"])
    host = hosts[0] if hosts else ""
    
    # Get upstream components, protocol and DNS resolver
    upstream_host = ""
    upstream_port = 80
    upstream_protocol = "http"
    dns_resolver = None
    
    def find_upstream_and_resolver(handlers):
        nonlocal upstream_host, upstream_port, upstream_protocol, dns_resolver
        for handler in handlers:
            if handler.get("handler") == "reverse_proxy":
                upstreams = handler.get("upstreams", [])
                if upstreams and "dial" in upstreams[0]:
                    dial = upstreams[0]["dial"]
                    # Extract protocol from upstream dial URL and clean upstream address
                    if dial.startswith("https://"):
                        upstream_protocol = "https"
                        upstream_addr = dial.replace("https://", "")
                    elif dial.startswith("http://"):
                        upstream_protocol = "http" 
                        upstream_addr = dial.replace("http://", "")
                    else:
                        upstream_protocol = "http"
                        upstream_addr = dial
                    
                    # Split host and port
                    if ":" in upstream_addr:
                        upstream_host, port_str = upstream_addr.rsplit(":", 1)
                        try:
                            upstream_port = int(port_str)
                        except ValueError:
                            upstream_port = 80
                    else:
                        upstream_host = upstream_addr
                        upstream_port = 80
                        
                # Extract DNS resolver info from transport configuration
                transport = handler.get("transport", {})
                if transport.get("resolver", {}).get("addresses"):
                    addresses = transport["resolver"]["addresses"]
                    dns_resolver = ", ".join(addresses) if addresses else None
            elif handler.get("handler") == "subroute":
                subroutes = handler.get("routes", [])
                for subroute in subroutes:
                    find_upstream_and_resolver(subroute.get("handle", []))
    
    find_upstream_and_resolver(route.get("handle", []))
    
    return {
        "host": host,
        "upstream_host": upstream_host,
        "upstream_port": upstream_port,
        "upstream_protocol": upstream_protocol,
        "dns_resolver": dns_resolver
    }

# Host management helper functions
HOSTS_CONFIG_PATH = "/config/hosts.yml"

async def load_hosts_config() -> Dict[str, Any]:
    """Load hosts configuration from YAML file"""
    try:
        if os.path.exists(HOSTS_CONFIG_PATH):
            with open(HOSTS_CONFIG_PATH, 'r') as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error loading hosts config: {e}")
    
    # Return default structure
    return {
        'defaults': {
            'user': 'revp',
            'port': 22,
            'key_file': '/app/ssh-keys/docker_monitor_key',
            'enabled': True
        },
        'hosts': {}
    }

async def save_hosts_config(config: Dict[str, Any]) -> None:
    """Save hosts configuration to YAML file"""
    try:
        os.makedirs(os.path.dirname(HOSTS_CONFIG_PATH), exist_ok=True)
        with open(HOSTS_CONFIG_PATH, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info("Hosts configuration saved successfully")
    except Exception as e:
        logger.error(f"Error saving hosts config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save hosts configuration: {e}")

async def test_host_ssh_connection(host_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test SSH connection to a host"""
    try:
        import subprocess
        import shlex
        
        # Build SSH command
        cmd_parts = [
            "ssh", 
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-p", str(host_data.get('port', 22)),
            "-i", host_data.get('key_file', '/app/ssh-keys/docker_monitor_key'),
            f"{host_data.get('user', 'revp')}@{host_data['hostname']}",
            "echo 'DCRP_CONNECTION_TEST_SUCCESS'"
        ]
        
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and "DCRP_CONNECTION_TEST_SUCCESS" in result.stdout:
            return {"status": "success", "message": "SSH connection successful"}
        else:
            error_msg = result.stderr.strip() if result.stderr else "Connection failed"
            return {"status": "error", "message": f"SSH connection failed: {error_msg}"}
            
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Connection timeout"}
    except Exception as e:
        return {"status": "error", "message": f"Connection test failed: {str(e)}"}

# Log parsing and monitoring functions
LOG_FILES = {
    'access': '/var/log/caddy/access.log',  # Admin API requests
    'admin': '/var/log/caddy/admin.log',    # Reverse proxy traffic for admin.domain.com
    'api': '/var/log/caddy/api.log',        # Reverse proxy traffic for api.domain.com
    'proxy': '/var/log/caddy/admin.log'     # Main reverse proxy traffic (alias for admin)
}

async def read_log_file(log_type: str, lines: int = 100, route_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read and parse Caddy log files"""
    log_file = LOG_FILES.get(log_type)
    if not log_file:
        raise ValueError(f"Unknown log type: {log_type}")
    
    log_path = Path(log_file)
    if not log_path.exists():
        return []
    
    logs = []
    try:
        async with aiofiles.open(log_path, 'r') as f:
            content = await f.read()
            log_lines = content.strip().split('\n')[-lines:]
            
            for line in reversed(log_lines):
                if not line.strip():
                    continue
                try:
                    log_entry = json.loads(line)
                    # Add timestamp parsing
                    if 'ts' in log_entry:
                        log_entry['timestamp'] = datetime.fromtimestamp(log_entry['ts']).isoformat()
                    
                    # Filter by route ID if specified
                    if route_id:
                        route_header = log_entry.get('request', {}).get('headers', {}).get('X-Dcrp-Route-Id', [''])
                        if route_header and route_header[0] != route_id:
                            continue
                    
                    logs.append(log_entry)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {e}")
    
    return logs

async def get_route_stats(route_id: Optional[str] = None) -> Dict[str, Any]:
    """Get route statistics from logs"""
    # Try to get logs from proxy (reverse proxy traffic) first, then fall back to access (admin API)
    logs = await read_log_file('proxy', lines=1000, route_id=route_id)
    if not logs:
        logs = await read_log_file('access', lines=1000, route_id=route_id)
    
    stats = {
        'total_requests': len(logs),
        'status_codes': {},
        'methods': {},
        'recent_activity': [],
        'response_times': []
    }
    for log in logs:
        # Handle different log formats
        if log.get('request'):
            # Reverse proxy log format
            status = log.get('status', 0)
            method = log.get('request', {}).get('method', 'GET')
            uri = log.get('request', {}).get('uri', '')
            remote_ip = log.get('request', {}).get('remote_ip') or log.get('request', {}).get('client_ip', '')
            duration = log.get('duration')
        else:
            # Admin API log format
            status = log.get('response', {}).get('status', 0)
            method = log.get('method', 'GET')
            uri = log.get('uri', '')
            remote_ip = log.get('remote_ip', '')
            duration = log.get('response', {}).get('duration')
        
        # Status codes
        stats['status_codes'][str(status)] = stats['status_codes'].get(str(status), 0) + 1
        
        # Methods
        stats['methods'][method] = stats['methods'].get(method, 0) + 1
        
        # Response times
        if duration:
            stats['response_times'].append(duration)
        
        # Recent activity (last 10)
        if len(stats['recent_activity']) < 10:
            stats['recent_activity'].append({
                'timestamp': log.get('timestamp', ''),
                'method': method,
                'uri': uri,
                'status': status,
                'remote_ip': remote_ip,
                'duration': duration
            })
    
    # Calculate average response time
    if stats['response_times']:
        stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
    
    return stats

async def stream_logs(log_type: str) -> str:
    """Stream live log updates"""
    log_file = LOG_FILES.get(log_type)
    if not log_file:
        return
    
    log_path = Path(log_file)
    if not log_path.exists():
        return
    
    # Simple tail implementation - in production, use a more robust solution
    try:
        async with aiofiles.open(log_path, 'r') as f:
            # Go to end of file
            await f.seek(0, 2)
            
            while True:
                line = await f.readline()
                if line:
                    try:
                        log_entry = json.loads(line.strip())
                        if 'ts' in log_entry:
                            log_entry['timestamp'] = datetime.fromtimestamp(log_entry['ts']).isoformat()
                        yield f"data: {json.dumps(log_entry)}\n\n"
                    except json.JSONDecodeError:
                        continue
                else:
                    await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Error streaming log file {log_file}: {e}")

# Static Routes Management
async def load_static_routes() -> Dict[str, Any]:
    """Load static routes from YAML file"""
    try:
        static_routes_path = os.path.join(config.config_path, 'static-routes.yml')
        if not os.path.exists(static_routes_path):
            return {}
            
        async with aiofiles.open(static_routes_path, 'r') as f:
            content = await f.read()
            static_config = yaml.safe_load(content) or {}
            return static_config.get('static_routes', {})
    except Exception as e:
        logger.error(f"Failed to load static routes: {e}")
        return {}

async def save_static_routes(static_routes: Dict[str, Any]) -> bool:
    """Save static routes to YAML file"""
    try:
        static_routes_path = os.path.join(config.config_path, 'static-routes.yml')
        
        # Load existing config to preserve other sections
        existing_config = {}
        if os.path.exists(static_routes_path):
            async with aiofiles.open(static_routes_path, 'r') as f:
                content = await f.read()
                existing_config = yaml.safe_load(content) or {}
        
        # Update static_routes section
        existing_config['static_routes'] = static_routes
        
        # Write back to file
        async with aiofiles.open(static_routes_path, 'w') as f:
            yaml_content = yaml.dump(existing_config, default_flow_style=False, sort_keys=False)
            await f.write(yaml_content)
            
        logger.info(f"Saved {len(static_routes)} static routes to config file")
        return True
    except Exception as e:
        logger.error(f"Failed to save static routes: {e}")
        return False

async def add_static_route(route_id: str, route_data: RouteCreate) -> bool:
    """Add a static route to the config file"""
    try:
        static_routes = await load_static_routes()
        
        # Convert route data to config format
        route_config = {
            'host': route_data.host,
            'upstream_protocol': route_data.upstream_protocol,
            'upstream_host': route_data.upstream_host,
            'upstream_port': route_data.upstream_port,
            'description': f"Static route added via API"
        }
        
        # Store the original route_id if it was custom (not auto-generated)
        if route_data.route_id:
            route_config['route_id'] = route_data.route_id
        
        static_routes[route_id] = route_config
        return await save_static_routes(static_routes)
    except Exception as e:
        logger.error(f"Failed to add static route: {e}")
        return False

async def remove_static_route(route_id: str) -> bool:
    """Remove a static route from the config file"""
    try:
        static_routes = await load_static_routes()
        if route_id in static_routes:
            del static_routes[route_id]
            return await save_static_routes(static_routes)
        return True  # Route already doesn't exist
    except Exception as e:
        logger.error(f"Failed to remove static route: {e}")
        return False

async def load_and_apply_static_routes():
    """Load static routes from config file and apply them to Caddy"""
    try:
        static_routes = await load_static_routes()
        if not static_routes:
            logger.info("No static routes found in config file")
            return

        logger.info(f"Loading {len(static_routes)} static routes from config file")
        
        # Get current routes once at the beginning for efficiency
        client = await get_caddy_client()
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(config.default_server)}")
        response.raise_for_status()
        current_routes = response.json()
        
        # Create a set of existing route IDs for efficient lookup
        existing_route_ids = {route.get("@id") for route in current_routes if route.get("@id")}
        existing_hosts = set()
        for route in current_routes:
            for match in route.get("match", []):
                existing_hosts.update(match.get("host", []))
        
        routes_to_add = []
        
        for route_id, route_config in static_routes.items():
            try:
                # Use stored route_id if available, otherwise use config key with static_ prefix
                stored_route_id = route_config.get('route_id')
                if stored_route_id:
                    # Use the original custom route_id, ensuring static_ prefix
                    final_route_id = f"static_{stored_route_id}" if not stored_route_id.startswith("static_") else stored_route_id
                else:
                    # Use config key with static_ prefix (legacy behavior)
                    final_route_id = f"static_{route_id}"
                
                # Create RouteCreate object from config
                route_data = RouteCreate(
                    host=route_config['host'],
                    upstream_protocol=route_config.get('upstream_protocol', 'http'),
                    upstream_host=route_config['upstream_host'],
                    upstream_port=route_config['upstream_port'],
                    route_id=stored_route_id,  # Pass original route_id to preserve it
                    source="static"
                )
                
                upstream = f"{route_config['upstream_host']}:{route_config['upstream_port']}"
                
                # Check if route already exists by ID
                if final_route_id in existing_route_ids:
                    logger.info(f"Static route already exists in Caddy: {final_route_id}")
                    continue
                
                # Check if host already exists (prevent duplicate hosts with different route IDs)
                if route_config['host'] in existing_hosts:
                    logger.warning(f"Host {route_config['host']} already configured, skipping route {route_id}")
                    continue
                
                # Create the route
                new_route = build_reverse_proxy_route(
                    route_data.host, route_data.upstream_host, route_data.upstream_port, final_route_id, route_data.upstream_protocol
                )
                
                routes_to_add.append(new_route)
                existing_route_ids.add(final_route_id)
                existing_hosts.add(route_config['host'])
                
                logger.info(f"Prepared static route: {route_id} -> {route_config['host']} -> {upstream}")
                    
            except Exception as e:
                logger.error(f"Failed to prepare static route {route_id}: {e}")
                continue
        
        # Apply all new routes in a single batch update
        if routes_to_add:
            try:
                # Prepend new routes (higher priority)
                updated_routes = routes_to_add + current_routes
                
                # Update routes in Caddy with fresh ETag
                response = await client.get(f"{config.caddy_admin_url}{server_routes_path(config.default_server)}")
                response.raise_for_status()
                etag = response.headers.get("etag")
                headers = {"If-Match": etag} if etag else {}
                
                response = await client.patch(
                    f"{config.caddy_admin_url}{server_routes_path(config.default_server)}",
                    json=updated_routes,
                    headers=headers
                )
                response.raise_for_status()
                
                logger.info(f"Successfully applied {len(routes_to_add)} static routes to Caddy")
            except Exception as e:
                logger.error(f"Failed to apply static routes batch update: {e}")
        else:
            logger.info("No new static routes to apply")
                
        logger.info("Finished applying static routes")
        
    except Exception as e:
        logger.error(f"Failed to load static routes: {e}")

# API Routes
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        client = await get_caddy_client()
        response = await client.get(f"{config.caddy_admin_url}/config/")
        response.raise_for_status()
        status_msg = "healthy"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        status_msg = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status=status_msg,
        caddy_admin_url=config.caddy_admin_url,
        server=config.default_server,
        dns_resolver=config.dns_resolver
    )

@app.get("/routes", response_model=List[RouteResponse])
async def list_routes(server: Optional[str] = Query(None)):
    """List all routes"""
    server = server or config.default_server
    
    try:
        client = await get_caddy_client()
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(server)}")
        response.raise_for_status()
        routes = response.json()
        
        result = []
        for idx, route in enumerate(routes):
            if not route.get("@id"):
                continue  # Skip routes without ID
                
            route_info = extract_route_info(route)
            # Determine source based on route_id pattern
            route_id = route["@id"]
            source = "monitor" if route_id.startswith("monitor_") else "static"
            
            result.append(RouteResponse(
                route_id=route_id,
                index=idx,
                host=route_info["host"],
                upstream_host=route_info["upstream_host"],
                upstream_port=route_info["upstream_port"],
                upstream_protocol=route_info["upstream_protocol"],
                terminal=bool(route.get("terminal", False)),
                source=source,
                dns_resolver=route_info["dns_resolver"]
            ))
        
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to list routes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to communicate with Caddy: {e}")

@app.post("/routes", response_model=Dict[str, str])
async def create_route(route: RouteCreate, server: Optional[str] = Query(None)):
    """Create a new route"""
    server = server or config.default_server
    
    # Generate route ID if not provided - always use static_ prefix for static routes
    if route.route_id:
        # If user provided a custom route_id, ensure it has static_ prefix for static routes
        route_id = f"static_{route.route_id}" if route.source == "static" and not route.route_id.startswith("static_") else route.route_id
    else:
        # Auto-generate route ID
        base_name = route.host.replace('.', '_').replace('*', 'star')
        route_id = f"static_{base_name}" if route.source == "static" else f"route_{base_name}"
    
    # Validate input
    if not route.host or not route.upstream:
        raise HTTPException(status_code=400, detail="Host and upstream are required")
    
    if "://" in route.host:
        raise HTTPException(status_code=400, detail="Host should not contain protocol")
    
    try:
        client = await get_caddy_client()
        
        # Get current routes with ETag
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(server)}")
        response.raise_for_status()
        current_routes = response.json()
        etag = response.headers.get("etag")
        
        # Check for duplicate route ID
        for existing_route in current_routes:
            if existing_route.get("@id") == route_id:
                raise HTTPException(
                    status_code=409, 
                    detail=f"Route ID '{route_id}' already exists"
                )
        
        # Check for duplicate hostname
        for existing_route in current_routes:
            for match in existing_route.get("match", []):
                existing_hosts = match.get("host", [])
                if route.host in existing_hosts:
                    raise HTTPException(
                        status_code=409, 
                        detail=f"Host '{route.host}' is already configured in route '{existing_route.get('@id')}'"
                    )
        
        # Build new route
        new_route = build_reverse_proxy_route(
            route.host, route.upstream_host, route.upstream_port, route_id, route.upstream_protocol
        )
        
        # Prepend new route (higher priority)
        updated_routes = [new_route] + current_routes
        
        # Update routes with concurrency control
        headers = {"If-Match": etag} if etag else {}
        response = await client.patch(
            f"{config.caddy_admin_url}{server_routes_path(server)}",
            json=updated_routes,
            headers=headers
        )
        response.raise_for_status()
        
        # If this is a static route (not from monitor), save to config file
        if route.source == "static":
            # Remove static_ prefix for config file storage
            config_route_id = route_id.replace("static_", "")
            await add_static_route(config_route_id, route)
            logger.info(f"Saved static route to config: {config_route_id}")
        
        logger.info(f"Created route: {route_id} -> {route.host} -> {route.upstream}")
        return {"status": "created", "route_id": route_id}
        
    except httpx.HTTPError as e:
        if hasattr(e, 'response') and e.response and e.response.status_code in (409, 412):
            raise HTTPException(status_code=409, detail="Concurrent modification detected, please retry")
        logger.error(f"Failed to create route: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create route: {e}")

@app.get("/routes/{route_id}", response_model=RouteResponse)
async def get_route(route_id: str, server: Optional[str] = Query(None)):
    """Get a specific route by ID"""
    server = server or config.default_server
    
    try:
        client = await get_caddy_client()
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(server)}")
        response.raise_for_status()
        routes = response.json()
        
        for idx, route in enumerate(routes):
            if route.get("@id") == route_id:
                route_info = extract_route_info(route)
                return RouteResponse(
                    route_id=route_id,
                    index=idx,
                    host=route_info["host"],
                    upstream_host=route_info["upstream_host"],
                    upstream_port=route_info["upstream_port"],
                    upstream_protocol=route_info["upstream_protocol"],
                    terminal=bool(route.get("terminal", False)),
                    dns_resolver=route_info["dns_resolver"]
                )
        
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to get route: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get route: {e}")

@app.patch("/routes/{route_id}", response_model=Dict[str, str])
async def update_route(route_id: str, updates: RouteUpdate, server: Optional[str] = Query(None)):
    """Update an existing route"""
    server = server or config.default_server
    
    try:
        client = await get_caddy_client()
        
        # Get current routes with ETag
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(server)}")
        response.raise_for_status()
        current_routes = response.json()
        etag = response.headers.get("etag")
        
        # Find and update the route
        route_found = False
        for idx, route in enumerate(current_routes):
            if route.get("@id") == route_id:
                route_found = True
                
                # Get current route info
                current_info = extract_route_info(route)
                
                # Use provided values or keep current ones
                new_upstream_host = updates.upstream_host or current_info["upstream_host"]
                new_upstream_port = updates.upstream_port or current_info["upstream_port"]
                new_upstream_protocol = updates.upstream_protocol or current_info["upstream_protocol"]
                
                # Rebuild route with new configuration
                current_routes[idx] = build_reverse_proxy_route(
                    current_info["host"], new_upstream_host, new_upstream_port, route_id, new_upstream_protocol
                )
                break
        
        if not route_found:
            raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
        
        # Update routes
        headers = {"If-Match": etag} if etag else {}
        response = await client.patch(
            f"{config.caddy_admin_url}{server_routes_path(server)}",
            json=current_routes,
            headers=headers
        )
        response.raise_for_status()
        
        logger.info(f"Updated route: {route_id}")
        return {"status": "updated", "route_id": route_id}
        
    except httpx.HTTPError as e:
        if hasattr(e, 'response') and e.response and e.response.status_code in (409, 412):
            raise HTTPException(status_code=409, detail="Concurrent modification detected, please retry")
        logger.error(f"Failed to update route: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update route: {e}")

@app.delete("/routes/{route_id}", response_model=Dict[str, str])
async def delete_route(route_id: str, server: Optional[str] = Query(None)):
    """Delete a route by ID"""
    server = server or config.default_server
    
    try:
        client = await get_caddy_client()
        
        # Get current routes with ETag
        response = await client.get(f"{config.caddy_admin_url}{server_routes_path(server)}")
        response.raise_for_status()
        current_routes = response.json()
        etag = response.headers.get("etag")
        
        # Remove the route
        updated_routes = [route for route in current_routes if route.get("@id") != route_id]
        
        if len(updated_routes) == len(current_routes):
            raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
        
        # Update routes
        headers = {"If-Match": etag} if etag else {}
        response = await client.patch(
            f"{config.caddy_admin_url}{server_routes_path(server)}",
            json=updated_routes,
            headers=headers
        )
        response.raise_for_status()
        
        # If this is a static route, remove it from config file
        if route_id.startswith("static_"):
            config_route_id = route_id.replace("static_", "")
            await remove_static_route(config_route_id)
            logger.info(f"Removed static route from config: {config_route_id}")
        
        logger.info(f"Deleted route: {route_id}")
        return {"status": "deleted", "route_id": route_id}
        
    except httpx.HTTPError as e:
        if hasattr(e, 'response') and e.response and e.response.status_code in (409, 412):
            raise HTTPException(status_code=409, detail="Concurrent modification detected, please retry")
        logger.error(f"Failed to delete route: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete route: {e}")

@app.get("/config")
async def get_caddy_config():
    """Get full Caddy configuration (debug endpoint)"""
    try:
        client = await get_caddy_client()
        response = await client.get(f"{config.caddy_admin_url}/config/")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Caddy config: {e}")

# Hosts management API endpoints
@app.get("/hosts", response_model=List[HostResponse])
async def list_hosts():
    """Get all configured hosts"""
    try:
        config = await load_hosts_config()
        hosts = []
        
        # Load host status data
        status_data = {}
        if os.path.exists(HOST_STATUS_FILE):
            try:
                async with aiofiles.open(HOST_STATUS_FILE, 'r') as f:
                    content = await f.read()
                    if content:
                        status_data = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load host status: {e}")
        
        for host_id, host_config in config.get('hosts', {}).items():
            # Merge with defaults
            defaults = config.get('defaults', {})
            host_data = {**defaults, **host_config, 'host_id': host_id}
            
            # Get status info for this host
            host_status = status_data.get(host_id, {})
            
            # Determine display status
            if not host_data.get('enabled', True):
                status = "disabled"
            elif host_status.get('status') == 'error':
                status = f"error: {host_status.get('message', 'Unknown error')}"
            elif host_status.get('status') == 'success':
                status = "connected"
            else:
                status = "unknown"
            
            hosts.append(HostResponse(
                host_id=host_id,
                hostname=host_data.get('hostname', ''),
                user=host_data.get('user', 'revp'),
                port=host_data.get('port', 22),
                key_file=host_data.get('key_file', '/app/ssh-keys/docker_monitor_key'),
                description=host_data.get('description'),
                enabled=host_data.get('enabled', True),
                status=status,
                last_seen=host_status.get('last_check')
            ))
        
        return hosts
    except Exception as e:
        logger.error(f"Failed to list hosts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list hosts: {e}")

@app.post("/hosts", response_model=Dict[str, str])
async def create_host(host: HostCreate):
    """Add a new host"""
    try:
        config = await load_hosts_config()
        
        # Check if host already exists
        if host.host_id in config.get('hosts', {}):
            raise HTTPException(status_code=400, detail=f"Host {host.host_id} already exists")
        
        # Add new host
        if 'hosts' not in config:
            config['hosts'] = {}
            
        config['hosts'][host.host_id] = {
            'hostname': host.hostname,
            'user': host.user,
            'port': host.port,
            'key_file': host.key_file,
            'description': host.description,
            'enabled': host.enabled
        }
        
        await save_hosts_config(config)
        logger.info(f"Host {host.host_id} added successfully")
        
        return {"message": f"Host {host.host_id} created successfully", "host_id": host.host_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create host: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create host: {e}")

@app.get("/hosts/{host_id}", response_model=HostResponse)
async def get_host(host_id: str):
    """Get specific host details"""
    try:
        config = await load_hosts_config()
        hosts = config.get('hosts', {})
        
        if host_id not in hosts:
            raise HTTPException(status_code=404, detail=f"Host {host_id} not found")
        
        host_config = hosts[host_id]
        defaults = config.get('defaults', {})
        host_data = {**defaults, **host_config, 'host_id': host_id}
        
        return HostResponse(
            host_id=host_id,
            hostname=host_data.get('hostname', ''),
            user=host_data.get('user', 'revp'),
            port=host_data.get('port', 22),
            key_file=host_data.get('key_file', '/app/ssh-keys/docker_monitor_key'),
            description=host_data.get('description'),
            enabled=host_data.get('enabled', True),
            status="enabled" if host_data.get('enabled', True) else "disabled"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get host: {e}")

@app.patch("/hosts/{host_id}", response_model=Dict[str, str])
async def update_host(host_id: str, updates: HostUpdate):
    """Update existing host"""
    try:
        config = await load_hosts_config()
        hosts = config.get('hosts', {})
        
        if host_id not in hosts:
            raise HTTPException(status_code=404, detail=f"Host {host_id} not found")
        
        # Update only provided fields
        host_config = hosts[host_id]
        if updates.hostname is not None:
            host_config['hostname'] = updates.hostname
        if updates.user is not None:
            host_config['user'] = updates.user
        if updates.port is not None:
            host_config['port'] = updates.port
        if updates.key_file is not None:
            host_config['key_file'] = updates.key_file
        if updates.description is not None:
            host_config['description'] = updates.description
        if updates.enabled is not None:
            host_config['enabled'] = updates.enabled
        
        await save_hosts_config(config)
        logger.info(f"Host {host_id} updated successfully")
        
        return {"message": f"Host {host_id} updated successfully", "host_id": host_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update host: {e}")

@app.delete("/hosts/{host_id}", response_model=Dict[str, str])
async def delete_host(host_id: str):
    """Remove a host"""
    try:
        config = await load_hosts_config()
        hosts = config.get('hosts', {})
        
        if host_id not in hosts:
            raise HTTPException(status_code=404, detail=f"Host {host_id} not found")
        
        # Remove the host
        del hosts[host_id]
        await save_hosts_config(config)
        
        logger.info(f"Host {host_id} deleted successfully")
        return {"message": f"Host {host_id} deleted successfully", "host_id": host_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete host: {e}")

@app.post("/hosts/{host_id}/test", response_model=Dict[str, str])
async def test_host_connection(host_id: str):
    """Test SSH connection to a host"""
    try:
        config = await load_hosts_config()
        hosts = config.get('hosts', {})
        
        if host_id not in hosts:
            raise HTTPException(status_code=404, detail=f"Host {host_id} not found")
        
        host_config = hosts[host_id]
        defaults = config.get('defaults', {})
        host_data = {**defaults, **host_config}
        
        # Test the connection
        test_result = await test_host_ssh_connection(host_data)
        
        # Store the test result in a status file
        await update_host_status(host_id, test_result)
        
        if test_result["status"] == "success":
            return {"message": f"Host {host_id} connection test successful", "host_id": host_id}
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Host {host_id} connection test failed: {test_result['message']}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test host connection: {e}")

# Host status tracking
HOST_STATUS_FILE = "/config/host-status.json"

async def update_host_status(host_id: str, status: Dict[str, Any]):
    """Update host status in status file"""
    try:
        # Load existing status
        status_data = {}
        if os.path.exists(HOST_STATUS_FILE):
            async with aiofiles.open(HOST_STATUS_FILE, 'r') as f:
                content = await f.read()
                if content:
                    status_data = json.loads(content)
        
        # Update status for this host
        status_data[host_id] = {
            "status": status["status"],
            "message": status.get("message", ""),
            "last_check": datetime.now().isoformat(),
            "last_success": datetime.now().isoformat() if status["status"] == "success" else status_data.get(host_id, {}).get("last_success")
        }
        
        # Save updated status
        async with aiofiles.open(HOST_STATUS_FILE, 'w') as f:
            await f.write(json.dumps(status_data, indent=2))
            
    except Exception as e:
        logger.error(f"Failed to update host status: {e}")

@app.post("/hosts/{host_id}/status")
async def report_host_status(host_id: str, request: Request):
    """Report host status from monitor service"""
    try:
        status = await request.json()
        await update_host_status(host_id, status)
        return {"message": "Status updated", "host_id": host_id}
    except Exception as e:
        logger.error(f"Failed to report host status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to report host status: {e}")

# Logging API endpoints
@app.get("/api/logs")
async def get_logs(
    log_type: str = Query("access", description="Log type: access, admin, api"),
    lines: int = Query(100, description="Number of lines to return"),
    route_id: Optional[str] = Query(None, description="Filter by route ID")
):
    """Get logs from Caddy log files"""
    try:
        logs = await read_log_file(log_type, lines, route_id)
        return {
            "log_type": log_type,
            "total": len(logs),
            "logs": logs
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")

@app.get("/api/logs/route/{route_id}")
async def get_route_logs(
    route_id: str,
    lines: int = Query(100, description="Number of lines to return")
):
    """Get logs for a specific route"""
    try:
        logs = await read_log_file("access", lines, route_id)
        return {
            "route_id": route_id,
            "total": len(logs),
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Failed to get route logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get route logs: {e}")

@app.get("/api/logs/stream")
async def stream_log_updates(
    log_type: str = Query("access", description="Log type to stream")
):
    """Stream live log updates via Server-Sent Events"""
    try:
        return StreamingResponse(
            stream_logs(log_type),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stream logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream logs: {e}")

@app.get("/api/stats/routes")
async def get_all_route_stats():
    """Get statistics for all routes"""
    try:
        # Get global stats only for now (route-specific stats will be added later)
        global_stats = await get_route_stats()
        route_stats = {}
        
        return {
            "global": global_stats,
            "routes": route_stats
        }
    except Exception as e:
        logger.error(f"Failed to get route statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get route statistics: {e}")

@app.get("/api/stats/route/{route_id}")
async def get_route_statistics(route_id: str):
    """Get detailed statistics for a specific route"""
    try:
        stats = await get_route_stats(route_id)
        return {
            "route_id": route_id,
            **stats
        }
    except Exception as e:
        logger.error(f"Failed to get route statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get route statistics: {e}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": exc.detail}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": exc.detail}
    )

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting DCRP API Server on {API_HOST}:{API_PORT}")
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info"
    )