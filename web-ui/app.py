#!/usr/bin/env python3
"""
DCRP Web UI - Flask application for managing reverse proxy routes
Provides a clean web interface for route management
"""

import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import httpx
import requests

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

@app.context_processor
def inject_file_info():
    """Inject file modification times for templates"""
    def get_current_template_mtime():
        try:
            # Try to get the template name from request endpoint
            endpoint = request.endpoint
            template_map = {
                'dashboard': 'dashboard.html',
                'routes': 'routes.html',
                'new_route_form': 'route_form.html', 
                'edit_route_form': 'route_form.html',
                'hosts_dashboard': 'hosts.html',
                'new_host_form': 'host_form.html',
                'edit_host_form': 'host_form.html'
            }
            
            template_name = template_map.get(endpoint, 'base.html')
            template_path = os.path.join(app.template_folder, template_name)
            
            if os.path.exists(template_path):
                mtime = os.path.getmtime(template_path)
                return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M UTC')
            return "Unknown"
        except Exception:
            return "Unknown"
    
    return dict(current_template_mtime=get_current_template_mtime())

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
    
    # Hosts management methods
    async def list_hosts(self) -> List[Dict[str, Any]]:
        """Get all configured hosts"""
        result = await self._request('GET', '/hosts')
        return result if isinstance(result, list) else []
    
    async def get_host(self, host_id: str) -> Dict[str, Any]:
        """Get specific host details"""
        return await self._request('GET', f'/hosts/{host_id}')
    
    async def create_host(self, host_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new host"""
        return await self._request('POST', '/hosts', json=host_data)
    
    async def update_host(self, host_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing host"""
        return await self._request('PATCH', f'/hosts/{host_id}', json=updates)
    
    async def delete_host(self, host_id: str) -> Dict[str, Any]:
        """Remove a host"""
        return await self._request('DELETE', f'/hosts/{host_id}')
    
    async def test_host_connection(self, host_id: str) -> Dict[str, Any]:
        """Test connection to a host"""
        return await self._request('POST', f'/hosts/{host_id}/test')

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

@app.route('/routes')
def routes():
    """Routes page showing all routes"""
    try:
        routes = safe_async(api_client.list_routes())
        return render_template('routes.html', routes=routes)
    except Exception as e:
        logger.error(f"Routes page error: {e}")
        flash(f"Error loading routes: {e}", 'error')
        return render_template('routes.html', routes=[], error=str(e))

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
            'upstream_protocol': request.form.get('protocol', 'http'),
            'upstream_host': request.form.get('hostname', '').strip(),
            'upstream_port': int(request.form.get('port', 80)),
            'route_id': request.form.get('route_id', '').strip() or None
        }
        
        # Validation
        if not route_data['host'] or not route_data['upstream_host'] or not route_data['upstream_port']:
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
        
        if request.form.get('hostname'):
            updates['upstream_host'] = request.form.get('hostname').strip()
            
        if request.form.get('port'):
            updates['upstream_port'] = int(request.form.get('port'))
        
        if request.form.get('protocol'):
            updates['upstream_protocol'] = request.form.get('protocol')
        
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

# Hosts management routes
@app.route('/hosts')
def hosts_dashboard():
    """Hosts management dashboard"""
    try:
        hosts = safe_async(api_client.list_hosts())
        return render_template('hosts.html', hosts=hosts)
    except Exception as e:
        logger.error(f"Error loading hosts: {e}")
        flash(f"Error loading hosts: {e}", 'error')
        return render_template('hosts.html', hosts=[])

@app.route('/hosts/new')
def new_host_form():
    """Show form for adding new host"""
    return render_template('host_form.html', host=None, action='create')

@app.route('/hosts/<host_id>/edit')
def edit_host_form(host_id):
    """Show form for editing existing host"""
    try:
        host = safe_async(api_client.get_host(host_id))
        return render_template('host_form.html', host=host, action='edit')
    except Exception as e:
        logger.error(f"Error loading host {host_id}: {e}")
        flash(f"Error loading host: {e}", 'error')
        return redirect(url_for('hosts_dashboard'))

@app.route('/hosts', methods=['POST'])
def create_host():
    """Handle host creation form submission"""
    try:
        host_data = {
            'host_id': request.form.get('host_id', '').strip(),
            'hostname': request.form.get('hostname', '').strip(),
            'user': request.form.get('user', '').strip(),
            'port': int(request.form.get('port', 22)),
            'key_file': request.form.get('key_file', '').strip(),
            'description': request.form.get('description', '').strip(),
            'enabled': 'enabled' in request.form
        }
        
        # Validation
        if not host_data['host_id'] or not host_data['hostname']:
            flash('Host ID and hostname are required', 'error')
            return redirect(url_for('new_host_form'))
        
        result = safe_async(api_client.create_host(host_data))
        flash(f"Host added successfully: {host_data['host_id']}", 'success')
        return redirect(url_for('hosts_dashboard'))
        
    except Exception as e:
        logger.error(f"Error creating host: {e}")
        flash(f"Error creating host: {e}", 'error')
        return redirect(url_for('new_host_form'))

@app.route('/hosts/<host_id>', methods=['POST'])
def update_host(host_id):
    """Handle host update form submission"""
    try:
        updates = {
            'hostname': request.form.get('hostname', '').strip(),
            'user': request.form.get('user', '').strip(),
            'port': int(request.form.get('port', 22)),
            'key_file': request.form.get('key_file', '').strip(),
            'description': request.form.get('description', '').strip(),
            'enabled': 'enabled' in request.form
        }
        
        result = safe_async(api_client.update_host(host_id, updates))
        flash(f"Host updated successfully: {host_id}", 'success')
        return redirect(url_for('hosts_dashboard'))
        
    except Exception as e:
        logger.error(f"Error updating host {host_id}: {e}")
        flash(f"Error updating host: {e}", 'error')
        return redirect(url_for('edit_host_form', host_id=host_id))

@app.route('/hosts/<host_id>/delete', methods=['POST'])
def delete_host(host_id):
    """Handle host deletion"""
    try:
        result = safe_async(api_client.delete_host(host_id))
        flash(f"Host removed successfully: {host_id}", 'success')
    except Exception as e:
        logger.error(f"Error deleting host {host_id}: {e}")
        flash(f"Error deleting host: {e}", 'error')
    
    return redirect(url_for('hosts_dashboard'))

@app.route('/hosts/<host_id>/test', methods=['POST'])
def test_host(host_id):
    """Test connection to host"""
    try:
        result = safe_async(api_client.test_host_connection(host_id))
        flash(f"Host connection test successful: {host_id}", 'success')
    except Exception as e:
        logger.error(f"Error testing host {host_id}: {e}")
        flash(f"Host connection test failed: {e}", 'error')
    
    # Check where the request came from and redirect back there
    referer = request.headers.get('Referer', '')
    if f'/hosts/{host_id}/edit' in referer:
        # If from edit page, redirect back to edit page
        return redirect(url_for('edit_host_form', host_id=host_id))
    else:
        # Otherwise redirect to hosts dashboard
        return redirect(url_for('hosts_dashboard'))

# API endpoints for logging
@app.route('/api/logs')
def api_logs():
    """Get logs for AJAX requests"""
    try:
        log_type = request.args.get('log_type', 'access')
        lines = int(request.args.get('lines', '100'))
        route_id = request.args.get('route_id')
        
        # Build query parameters
        params = {'log_type': log_type, 'lines': lines}
        if route_id:
            params['route_id'] = route_id
        
        response = requests.get(f"{API_BASE_URL}/api/logs", params=params, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"API logs error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/routes')
def api_stats_routes():
    """Get route statistics for AJAX requests"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/routes", timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"API stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/route/<route_id>')
def api_stats_route(route_id):
    """Get statistics for a specific route"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats/route/{route_id}", timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"API stats error for route {route_id}: {e}")
        return jsonify({'error': str(e)}), 500

# API endpoints for hosts
@app.route('/api/hosts')
def api_hosts():
    """Get hosts list for AJAX requests"""
    try:
        hosts = safe_async(api_client.list_hosts())
        return jsonify(hosts)
    except Exception as e:
        logger.error(f"API hosts error: {e}")
        return jsonify({'error': str(e)}), 500

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