# DCRP - Docker Container Reverse Proxy

A modern, modular reverse proxy system built with Caddy, designed for Docker container auto-discovery and management with Cloudflare DNS integration and Let's Encrypt SSL certificates.

## Features

🌐 **Automatic HTTPS** - Cloudflare DNS challenge with Let's Encrypt wildcard certificates  
🐳 **Container Auto-Discovery** - Automatically create routes for Docker containers with labels  
🔄 **Real-time Updates** - Dynamic route management via REST API  
🖥️ **Web Administration** - Clean, responsive web interface with sortable/resizable tables using [snadboy-table-lib](https://github.com/snadboy/snadboy-table-lib)  
🚀 **Multi-Host Support** - SSH-based monitoring of remote Docker hosts  
⚡ **High Performance** - Built with FastAPI, Flask, and Caddy  
🛡️ **Security First** - Force HTTPS, WebSocket support, security headers  
📊 **Health Monitoring** - Built-in health checks and monitoring  

## Quick Start

### 1. Clone and Configure

```bash
git clone <your-repo> dcrp
cd dcrp

# Copy and configure environment
cp .env.example .env
nano .env  # Edit with your settings
```

### 2. Configure Your Domain and Cloudflare

```bash
# Required environment variables in .env:
DOMAIN=example.com
LETS_ENCRYPT_EMAIL=admin@example.com
CLOUDFLARE_API_TOKEN=your-token-here
SECRET_KEY=$(openssl rand -hex 32)
```

### 3. Deploy the System

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access the Admin Panel

- **Web Interface**: https://admin.example.com
- **API Documentation**: https://api.example.com/docs
- **Caddy Admin**: http://localhost:2019

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Caddy Proxy   │───▶│   API Server     │───▶│   Web UI        │
│  (Port 80/443)  │    │   (FastAPI)      │    │   (Flask)       │
│                 │    │   Port 8000      │    │   Port 5000     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        ▲                       │
         │                        │                       │
         ▼                        │                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Docker Monitor │    │  SSH Manager     │    │  User Browser   │
│  (Auto-discover)│    │  (Remote hosts)  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Service Overview

### Caddy Reverse Proxy
- **Port**: 80, 443, 2019 (admin)
- **Purpose**: HTTPS termination, reverse proxying, certificate management
- **Features**: Cloudflare DNS, Let's Encrypt, automatic HTTPS

### API Server (FastAPI)
- **Port**: 8000
- **Purpose**: Route management API, Caddy configuration
- **Endpoints**: `/routes`, `/health`, `/config`

### Web UI (Flask)
- **Port**: 5000
- **Purpose**: Administrative dashboard for route management
- **Features**: Responsive design, real-time updates

### Docker Monitor
- **Purpose**: Auto-discovery of Docker containers with DCRP labels
- **Monitors**: Container start/stop events, label changes

### SSH Manager
- **Purpose**: Multi-host support via SSH connections
- **Features**: Remote Docker host monitoring, secure key-based auth

## Container Auto-Discovery

Add labels to your Docker containers for automatic route creation:

```yaml
# docker-compose.yml
services:
  my-app:
    image: my-app:latest
    labels:
      - "dcrp.enable=true"
      - "dcrp.host=myapp.example.com"
      - "dcrp.port=3000"
      - "dcrp.ssl=true"        # Force HTTPS
      - "dcrp.websocket=true"  # Enable WebSocket support
```

## Manual Route Management

### Via Web Interface
1. Navigate to https://admin.example.com
2. Click "Add Route"
3. Fill in host, upstream, and options
4. Save

### Via API
```bash
# Create route
curl -X POST https://api.example.com/routes \
  -H "Content-Type: application/json" \
  -d '{
    "host": "api.example.com",
    "upstream": "backend:8080",
    "force_ssl": true,
    "websocket": false
  }'

# List routes
curl https://api.example.com/routes

# Delete route
curl -X DELETE https://api.example.com/routes/my-route-id
```

## Configuration Files

### Hosts Configuration (`config/hosts.yml`)
```yaml
hosts:
  local:
    enabled: true
    type: local
    docker_host: "unix:///var/run/docker.sock"
  
  remote-server:
    enabled: true
    type: ssh
    hostname: "192.168.1.100"
    username: "docker"
    ssh_key: "/app/ssh-keys/remote-server"
```

### Static Routes (`config/static-routes.yml`)
```yaml
static_routes:
  external-api:
    host: "external.example.com"
    upstream: "api.external.com:443"
    features:
      force_ssl: true
```

## Multi-Host SSH Setup

1. **Generate SSH Key**:
```bash
mkdir ssh-keys
ssh-keygen -t rsa -b 4096 -f ssh-keys/remote-host -N ""
```

2. **Copy Public Key to Remote Host**:
```bash
ssh-copy-id -i ssh-keys/remote-host.pub user@remote-host
```

3. **Update Configuration**:
```yaml
# config/hosts.yml
hosts:
  remote-host:
    enabled: true
    type: ssh
    hostname: "remote-host.example.com"
    username: "docker"
    ssh_key: "/app/ssh-keys/remote-host"
```

## Security Features

- **Automatic HTTPS**: All traffic redirected to HTTPS
- **Security Headers**: HSTS, CSP, X-Frame-Options
- **WebSocket Support**: Full WebSocket proxying capability
- **Rate Limiting**: Built-in request rate limiting
- **Secret Management**: Environment-based secrets

## Monitoring and Health Checks

- **Service Health**: `/health` endpoints for all services
- **Container Monitoring**: Real-time Docker event processing  
- **Log Aggregation**: Centralized logging with rotation
- **Metrics**: Built-in Prometheus-compatible metrics

## Troubleshooting

### Check Service Status
```bash
docker-compose ps
docker-compose logs api-server
docker-compose logs caddy
```

### Test API Connectivity
```bash
curl -f http://localhost:8000/health
curl -f http://localhost:5000/api/health
```

### Verify Caddy Configuration
```bash
curl http://localhost:2019/config/ | jq .
```

### Common Issues

1. **Cloudflare Token**: Ensure token has DNS:Edit permissions
2. **Domain DNS**: Verify domain points to your server
3. **Port Access**: Check firewall rules for ports 80/443
4. **SSH Keys**: Ensure proper permissions (600) on SSH keys

## Development

### Local Development
```bash
# Start core services only
docker-compose up caddy api-server web-ui

# Run monitor services separately for debugging
cd docker-monitor
python monitor.py

cd ../ssh-manager  
python ssh_config.py
```

### API Development
```bash
cd api-server
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Web UI Development
```bash
cd web-ui
pip install -r requirements.txt
export API_BASE_URL=http://localhost:8000
python app.py
```

### Table Library Integration

The web UI uses **snadboy-table-lib** for enhanced table functionality:

- **Repository**: https://github.com/snadboy/snadboy-table-lib  
- **Version**: v1.0.0
- **Features**: Column sorting, column resizing, zero dependencies
- **Location**: `web-ui/static/libs/snadboy-table/`

To update the table library:
```bash
# Download new version from GitHub releases
curl -L -o /tmp/table-lib.zip https://github.com/snadboy/snadboy-table-lib/archive/v1.0.0.zip
unzip /tmp/table-lib.zip
cp snadboy-table-lib-*/dist/* web-ui/static/libs/snadboy-table/
```

## Production Deployment

### Resource Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 2GB+ recommended  
- **Storage**: 10GB+ for logs and certificates
- **Network**: Ports 80, 443 accessible from internet

### Security Hardening
1. Change default secret keys
2. Use non-root users (already configured)
3. Enable firewall rules
4. Regular security updates
5. Monitor access logs

### Backup Strategy
- **Caddy Data**: `caddy_data` and `caddy_config` volumes
- **Configuration**: `config/` directory
- **SSL Certificates**: Automatically handled by Let's Encrypt

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## License

MIT License - see LICENSE file for details

## Support

- **Documentation**: Check this README and inline code comments
- **Issues**: Create GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions

---

**DCRP** - Docker Container Reverse Proxy v1.0.0  
Built with ❤️ using Caddy, FastAPI, Flask, and Docker