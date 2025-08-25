#!/usr/bin/env python3
"""
DCRP Web UI - Flask application for managing reverse proxy routes
Provides a clean web interface for route management
"""

import os
import logging
from typing import Optional, Dict, List, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dcrp-webui")

# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://api-server:8000')
WEB_PORT = int(os.environ.get('WEB_PORT', '5000'))
WEB_HOST = os.environ.get('WEB_HOST', '0.0.0.0')
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dcrp-default-secret-change-in-production')

class APIClient:
    """Client for communicating with DCRP API Server"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.timeout = 10.0
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to API server"""
        url = f"{self.base_url}{path}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"API request failed: {method} {url} - {e}")
                if hasattr(e, 'response') and e.response:
                    try:
                        error_data = e.response.json()
                        raise Exception(error_data.get('detail', str(e)))
                    except:
                        raise Exception(f"API Error: {e.response.status_code}")
                raise Exception(f"Connection Error: {e}")
    
    async def get_health(self) -> Dict[str, Any]:
        """Get API server health status"""
        return await self._request('GET', '/health')
    
    async def list_routes(self) -> List[Dict[str, Any]]:
        """Get all routes"""
        result = await self._request('GET', '/routes')
        return result if isinstance(result, list) else []
    
    async def get_route(self, route_id: str) -> Dict[str, Any]:
        """Get specific route details"""
        return await self._request('GET', f'/routes/{route_id}')
    
    async def create_route(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new route"""
        return await self._request('POST', '/routes', json=route_data)
    
    async def update_route(self, route_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing route"""
        return await self._request('PATCH', f'/routes/{route_id}', json=updates)
    
    async def delete_route(self, route_id: str) -> Dict[str, Any]:
        """Delete a route"""
        return await self._request('DELETE', f'/routes/{route_id}')

# Initialize API client
api_client = APIClient()

# Utility functions
def safe_async(coro):
    """Wrapper to run async functions in Flask routes"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# Routes
@app.route('/')
def dashboard():
    """Main dashboard showing all routes"""
    try:
        # Get health and routes data
        health = safe_async(api_client.get_health())
        routes = safe_async(api_client.list_routes())
        
        return render_template('dashboard.html', 
                             health=health, 
                             routes=routes,
                             api_url=API_BASE_URL)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash(f"Error loading dashboard: {e}", 'error')
        return render_template('dashboard.html', 
                             health={'status': 'error'}, 
                             routes=[],
                             error=str(e))

@app.route('/routes/new')
def new_route_form():
    """Show form for creating new route"""
    return render_template('route_form.html', route=None, action='create')

@app.route('/routes/<route_id>/edit')
def edit_route_form(route_id):
    """Show form for editing existing route"""
    try:
        route = safe_async(api_client.get_route(route_id))
        return render_template('route_form.html', route=route, action='edit')
    except Exception as e:
        logger.error(f"Error loading route {route_id}: {e}")
        flash(f"Error loading route: {e}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/routes', methods=['POST'])
def create_route():
    """Handle route creation form submission"""
    try:
        route_data = {
            'host': request.form.get('host', '').strip(),
            'upstream': request.form.get('upstream', '').strip(),
            'route_id': request.form.get('route_id', '').strip() or None,
            'force_ssl': 'force_ssl' in request.form,
            'websocket': 'websocket' in request.form
        }
        
        # Validation
        if not route_data['host'] or not route_data['upstream']:
            flash('Host and upstream are required', 'error')
            return redirect(url_for('new_route_form'))
        
        result = safe_async(api_client.create_route(route_data))
        flash(f"Route created successfully: {result.get('route_id')}", 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logger.error(f"Error creating route: {e}")
        flash(f"Error creating route: {e}", 'error')
        return redirect(url_for('new_route_form'))

@app.route('/routes/<route_id>', methods=['POST'])
def update_route(route_id):
    """Handle route update form submission"""
    try:
        updates = {}
        
        if request.form.get('upstream'):
            updates['upstream'] = request.form.get('upstream').strip()
        
        updates['force_ssl'] = 'force_ssl' in request.form
        updates['websocket'] = 'websocket' in request.form
        
        result = safe_async(api_client.update_route(route_id, updates))
        flash(f"Route updated successfully: {route_id}", 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logger.error(f"Error updating route {route_id}: {e}")
        flash(f"Error updating route: {e}", 'error')
        return redirect(url_for('edit_route_form', route_id=route_id))

@app.route('/routes/<route_id>/delete', methods=['POST'])
def delete_route(route_id):
    """Handle route deletion"""
    try:
        result = safe_async(api_client.delete_route(route_id))
        flash(f"Route deleted successfully: {route_id}", 'success')
    except Exception as e:
        logger.error(f"Error deleting route {route_id}: {e}")
        flash(f"Error deleting route: {e}", 'error')
    
    return redirect(url_for('dashboard'))

# API endpoints for AJAX requests
@app.route('/api/health')
def api_health():
    """Proxy health check to API server"""
    try:
        health = safe_async(api_client.get_health())
        return jsonify(health)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/routes')
def api_routes():
    """Get routes as JSON"""
    try:
        routes = safe_async(api_client.list_routes())
        return jsonify(routes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/routes/<route_id>')
def api_route_details(route_id):
    """Get specific route as JSON"""
    try:
        route = safe_async(api_client.get_route(route_id))
        return jsonify(route)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error_code=500, 
                         error_message="Internal server error"), 500

# Template filters
@app.template_filter('status_badge')
def status_badge_filter(status):
    """Convert status to Bootstrap badge class"""
    status_map = {
        'healthy': 'success',
        'ok': 'success',
        'error': 'danger',
        'unhealthy': 'danger',
        'warning': 'warning'
    }
    return status_map.get(status.lower(), 'secondary')

if __name__ == '__main__':
    logger.info(f"Starting DCRP Web UI on {WEB_HOST}:{WEB_PORT}")
    logger.info(f"API Base URL: {API_BASE_URL}")
    
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=DEBUG_MODE
    )