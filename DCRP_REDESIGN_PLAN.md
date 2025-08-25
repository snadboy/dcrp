# Docker Container Reverse Proxy (DCRP) - Redesigned Architecture

## Project Structure
```
dcrp/
├── docker-compose.yml          # Orchestrate all services
├── .env.example               # Environment template
├── caddy/                     # Pure reverse proxy with Let's Encrypt
│   ├── Caddyfile
│   └── Dockerfile
├── api-server/                # Caddy route management API
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── web-ui/                    # Administrative dashboard
│   ├── static/
│   ├── templates/
│   ├── app.py
│   └── Dockerfile
├── docker-monitor/            # Container discovery service
│   ├── monitor.py
│   ├── requirements.txt
│   └── Dockerfile
├── ssh-manager/               # SSH host management
│   ├── ssh_config.py
│   ├── requirements.txt
│   └── Dockerfile
├── config/                    # Shared configuration
│   ├── hosts.yml
│   └── static-routes.yml
└── docs/                      # Documentation
    ├── README.md
    ├── API.md
    └── DEPLOYMENT.md
```

## Core Requirements

### Caddy Reverse Proxy
- **Cloudflare DNS integration** for Let's Encrypt certificate management
- **Automatic HTTPS** with wildcard certificate support (*.domain.com)
- **Dynamic route configuration** via Admin API
- **WebSocket support** for real-time applications
- **Force SSL redirects** for security
- **Catch-all handlers** for unconfigured domains

## Implementation Plan

### Phase 1: Core Infrastructure
1. **Extract Caddy service** - Clean reverse proxy with Cloudflare DNS + Let's Encrypt
2. **Create API server** - Standalone FastAPI service for route management
3. **Build web UI** - Separate Flask/React frontend service
4. **Setup orchestration** - Docker Compose for service coordination

### Phase 2: Monitoring Services  
1. **Docker monitor service** - Container discovery and event handling
2. **SSH manager service** - Remote host connection management
3. **Configuration service** - Centralized config management
4. **Health monitoring** - Service health checks and metrics

### Phase 3: Integration & Polish
1. **Inter-service communication** - API contracts between services
2. **Event-driven updates** - Real-time route updates via events
3. **Comprehensive logging** - Centralized logging with structured data
4. **Documentation** - Complete API docs and deployment guides

## Benefits of New Architecture
- **Separation of concerns** - Each service has one responsibility
- **Independent scaling** - Scale services based on load
- **Easy maintenance** - Update services independently
- **Better testing** - Unit test each service in isolation
- **Flexible deployment** - Deploy only needed components
- **Technology flexibility** - Use best tool for each service

## Key Features from Original revp2
- Caddy reverse proxy with Admin API integration
- FastAPI route management with WebSocket and Force SSL support
- Flask web interface for route administration
- Docker container auto-discovery and routing
- SSH host management for multi-host deployments
- Cloudflare DNS + Let's Encrypt automatic HTTPS

This redesign maintains all current functionality while making the system modular, maintainable, and scalable.