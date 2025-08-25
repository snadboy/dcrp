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

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx

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

class Config:
    caddy_admin_url = CADDY_ADMIN_URL
    default_server = DEFAULT_SERVER
    timeout = 10.0

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
    upstream: str = Field(..., description="Backend service address (host:port)")
    route_id: Optional[str] = Field(None, description="Optional route identifier")
    force_ssl: bool = Field(False, description="Force HTTP to HTTPS redirect")
    websocket: bool = Field(False, description="Enable WebSocket support")

class RouteUpdate(BaseModel):
    upstream: Optional[str] = Field(None, description="New backend service address")
    force_ssl: Optional[bool] = Field(None, description="Force HTTP to HTTPS redirect")
    websocket: Optional[bool] = Field(None, description="Enable WebSocket support")

class RouteResponse(BaseModel):
    route_id: str
    host: str
    upstream: str
    index: int
    force_ssl: bool = False
    websocket: bool = False
    terminal: bool = False

class HealthResponse(BaseModel):
    status: str
    caddy_admin_url: str
    server: str
    version: str = "1.0.0"

# Helper functions
async def get_caddy_client() -> httpx.AsyncClient:
    """Get HTTP client for Caddy Admin API"""
    if not http_client:
        raise HTTPException(status_code=500, detail="HTTP client not initialized")
    return http_client

def server_routes_path(server: str) -> str:
    """Get API path for server routes"""
    return f"/config/apps/http/servers/{server}/routes"

def build_reverse_proxy_route(
    host: str, 
    upstream: str, 
    route_id: str,
    force_ssl: bool = False,
    websocket: bool = False
) -> Dict[str, Any]:
    """Build a Caddy reverse proxy route configuration"""
    
    if force_ssl:
        # HTTP to HTTPS redirect + HTTPS reverse proxy
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
                        "handle": [{
                            "handler": "reverse_proxy",
                            "upstreams": [{"dial": upstream}]
                        }]
                    }
                ]
            }]
        }
    else:
        # Simple reverse proxy
        route = {
            "@id": route_id,
            "match": [{"host": [host]}],
            "handle": [{
                "handler": "reverse_proxy",
                "upstreams": [{"dial": upstream}]
            }]
        }
    
    # Add WebSocket headers if needed
    if websocket:
        def add_websocket_headers(handlers):
            for handler in handlers:
                if handler.get("handler") == "reverse_proxy":
                    handler["headers"] = {
                        "request": {
                            "set": {
                                "Upgrade": ["{http.request.header.Upgrade}"],
                                "Connection": ["{http.request.header.Connection}"],
                                "Sec-WebSocket-Key": ["{http.request.header.Sec-WebSocket-Key}"],
                                "Sec-WebSocket-Version": ["{http.request.header.Sec-WebSocket-Version}"],
                                "Sec-WebSocket-Extensions": ["{http.request.header.Sec-WebSocket-Extensions}"]
                            }
                        }
                    }
                elif handler.get("handler") == "subroute":
                    for subroute in handler.get("routes", []):
                        add_websocket_headers(subroute.get("handle", []))
        
        add_websocket_headers(route["handle"])
    
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
    
    # Get upstream and detect features
    upstream = ""
    force_ssl = False
    websocket = False
    
    def find_upstream_and_features(handlers):
        nonlocal upstream, force_ssl, websocket
        for handler in handlers:
            if handler.get("handler") == "reverse_proxy":
                upstreams = handler.get("upstreams", [])
                if upstreams and "dial" in upstreams[0]:
                    upstream = upstreams[0]["dial"]
                # Check for WebSocket headers
                headers = handler.get("headers", {}).get("request", {}).get("set", {})
                if "Upgrade" in headers or "Connection" in headers:
                    websocket = True
            elif handler.get("handler") == "subroute":
                subroutes = handler.get("routes", [])
                for subroute in subroutes:
                    # Check for HTTP redirect (force SSL)
                    if subroute.get("match", [{}])[0].get("protocol") == "http":
                        force_ssl = True
                    find_upstream_and_features(subroute.get("handle", []))
    
    find_upstream_and_features(route.get("handle", []))
    
    return {
        "host": host,
        "upstream": upstream,
        "force_ssl": force_ssl,
        "websocket": websocket
    }

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
        server=config.default_server
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
            result.append(RouteResponse(
                route_id=route["@id"],
                index=idx,
                host=route_info["host"],
                upstream=route_info["upstream"],
                force_ssl=route_info["force_ssl"],
                websocket=route_info["websocket"],
                terminal=bool(route.get("terminal", False))
            ))
        
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to list routes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to communicate with Caddy: {e}")

@app.post("/routes", response_model=Dict[str, str])
async def create_route(route: RouteCreate, server: Optional[str] = Query(None)):
    """Create a new route"""
    server = server or config.default_server
    
    # Generate route ID if not provided
    route_id = route.route_id or f"route_{route.host.replace('.', '_').replace('*', 'star')}"
    
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
        
        # Build new route
        new_route = build_reverse_proxy_route(
            route.host, route.upstream, route_id, route.force_ssl, route.websocket
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
                    upstream=route_info["upstream"],
                    force_ssl=route_info["force_ssl"],
                    websocket=route_info["websocket"],
                    terminal=bool(route.get("terminal", False))
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
                new_upstream = updates.upstream or current_info["upstream"]
                new_force_ssl = updates.force_ssl if updates.force_ssl is not None else current_info["force_ssl"]
                new_websocket = updates.websocket if updates.websocket is not None else current_info["websocket"]
                
                # Rebuild route with new configuration
                current_routes[idx] = build_reverse_proxy_route(
                    current_info["host"], new_upstream, route_id, new_force_ssl, new_websocket
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