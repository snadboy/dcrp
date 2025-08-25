# DCRP - Docker Container Reverse Proxy
# Makefile for easy management and deployment

.PHONY: help build up down logs clean restart build-caddy build-api build-web build-monitor build-ssh

# Default target
help: ## Show this help message
	@echo "DCRP - Docker Container Reverse Proxy"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Environment setup
setup: ## Create .env file from template and setup SSH directory
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env file from template"; \
		echo "⚠️  Please edit .env with your configuration"; \
	else \
		echo "⚠️  .env file already exists"; \
	fi
	@mkdir -p ssh-keys
	@chmod 700 ssh-keys
	@echo "✅ SSH keys directory ready"

# Build commands
build: ## Build all Docker images
	@echo "🔨 Building all DCRP services..."
	docker-compose build

build-caddy: ## Build only Caddy service (with Cloudflare plugin)
	@echo "🔨 Building Caddy with Cloudflare DNS plugin..."
	docker-compose build caddy

build-api: ## Build only API server
	@echo "🔨 Building API server..."
	docker-compose build api-server

build-web: ## Build only Web UI
	@echo "🔨 Building Web UI..."
	docker-compose build web-ui

build-monitor: ## Build only Docker Monitor
	@echo "🔨 Building Docker Monitor..."
	docker-compose build docker-monitor

build-ssh: ## Build only SSH Manager
	@echo "🔨 Building SSH Manager..."
	docker-compose build ssh-manager

# Deployment commands
up: ## Start all services
	@echo "🚀 Starting DCRP services..."
	docker-compose up -d

up-core: ## Start only core services (Caddy, API, Web UI)
	@echo "🚀 Starting core DCRP services..."
	docker-compose up -d caddy api-server web-ui

up-dev: ## Start services in development mode (with logs)
	@echo "🚀 Starting DCRP services in development mode..."
	docker-compose up

down: ## Stop all services
	@echo "🛑 Stopping DCRP services..."
	docker-compose down

restart: ## Restart all services
	@echo "🔄 Restarting DCRP services..."
	docker-compose restart

# Monitoring commands
logs: ## Show logs from all services
	docker-compose logs -f

logs-caddy: ## Show Caddy logs
	docker-compose logs -f caddy

logs-api: ## Show API server logs
	docker-compose logs -f api-server

logs-web: ## Show Web UI logs
	docker-compose logs -f web-ui

logs-monitor: ## Show Docker Monitor logs
	docker-compose logs -f docker-monitor

logs-ssh: ## Show SSH Manager logs
	docker-compose logs -f ssh-manager

# Status and health commands
status: ## Show service status
	@echo "📊 DCRP Service Status:"
	@echo ""
	docker-compose ps

health: ## Check service health
	@echo "🏥 DCRP Health Check:"
	@echo ""
	@echo "API Server:"
	@curl -sf http://localhost:8000/health | jq . 2>/dev/null || echo "❌ API Server not responding"
	@echo ""
	@echo "Web UI:"
	@curl -sf http://localhost:5000/api/health | jq . 2>/dev/null || echo "❌ Web UI not responding"
	@echo ""
	@echo "Caddy Admin:"
	@curl -sf http://localhost:2019/config/apps/http | jq '.servers' 2>/dev/null || echo "❌ Caddy not responding"

# Development commands
dev-api: ## Run API server in development mode
	@echo "🔧 Starting API server in development mode..."
	@cd api-server && python -m pip install -r requirements.txt
	@cd api-server && python main.py

dev-web: ## Run Web UI in development mode
	@echo "🔧 Starting Web UI in development mode..."
	@cd web-ui && python -m pip install -r requirements.txt
	@cd web-ui && export API_BASE_URL=http://localhost:8000 && python app.py

dev-monitor: ## Run Docker Monitor in development mode
	@echo "🔧 Starting Docker Monitor in development mode..."
	@cd docker-monitor && python -m pip install -r requirements.txt
	@cd docker-monitor && python monitor.py

# Maintenance commands
clean: ## Remove all containers, networks, and volumes
	@echo "🧹 Cleaning up DCRP..."
	docker-compose down -v --remove-orphans
	docker system prune -f

clean-images: ## Remove all DCRP Docker images
	@echo "🧹 Removing DCRP Docker images..."
	docker images | grep dcrp | awk '{print $$3}' | xargs -r docker rmi -f

update: ## Pull latest base images and rebuild
	@echo "⬇️ Updating base images..."
	docker-compose pull
	@echo "🔨 Rebuilding services..."
	docker-compose build --no-cache

# Backup and restore
backup: ## Backup Caddy data and configuration
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@docker run --rm -v dcrp-caddy-data:/data -v dcrp-caddy-config:/config -v $(PWD)/backups:/backup busybox tar czf /backup/dcrp-backup-$(shell date +%Y%m%d_%H%M%S).tar.gz -C /data . -C /config .
	@echo "✅ Backup created in ./backups/"

# SSL and certificates
ssl-status: ## Check SSL certificate status
	@echo "🔒 SSL Certificate Status:"
	@curl -sf http://localhost:2019/config/apps/tls/certificates | jq '.[] | {subjects: .subjects, issuer: .issuer, not_after: .not_after}' 2>/dev/null || echo "❌ Could not retrieve certificate info"

# Configuration validation
validate-config: ## Validate Caddy configuration
	@echo "✅ Validating Caddy configuration..."
	@docker-compose exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

# Quick deployment (for production)
deploy: setup build up ## Complete deployment: setup, build, and start

# Testing
test: ## Run basic connectivity tests
	@echo "🧪 Running DCRP tests..."
	@echo "Testing API server..."
	@curl -sf http://localhost:8000/health >/dev/null && echo "✅ API server OK" || echo "❌ API server FAILED"
	@echo "Testing Web UI..."
	@curl -sf http://localhost:5000/api/health >/dev/null && echo "✅ Web UI OK" || echo "❌ Web UI FAILED"
	@echo "Testing Caddy admin..."
	@curl -sf http://localhost:2019/config >/dev/null && echo "✅ Caddy admin OK" || echo "❌ Caddy admin FAILED"

# Show important URLs
urls: ## Show important service URLs
	@echo "🌐 DCRP Service URLs:"
	@echo ""
	@echo "Web Admin Panel:    https://admin.$(shell grep DOMAIN= .env 2>/dev/null | cut -d'=' -f2 || echo 'your-domain.com')"
	@echo "API Documentation:  https://api.$(shell grep DOMAIN= .env 2>/dev/null | cut -d'=' -f2 || echo 'your-domain.com')/docs"
	@echo "Caddy Admin API:    http://localhost:2019"
	@echo ""
	@echo "Local Development:"
	@echo "API Server:         http://localhost:8000"
	@echo "Web UI:             http://localhost:5000"