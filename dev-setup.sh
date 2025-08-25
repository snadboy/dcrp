#!/bin/bash
# DCRP Development Setup Script
# Run Python services locally for development

set -e

echo "🚀 Setting up DCRP for local development..."

# Check if Python 3.11+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python version: $PYTHON_VERSION"

# Function to setup virtual environment and install dependencies
setup_service() {
    local service_name=$1
    local service_dir=$2
    
    echo "📦 Setting up $service_name..."
    
    cd "$service_dir"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    
    cd ..
    echo "✅ $service_name setup complete"
}

# Setup each Python service
setup_service "API Server" "api-server"
setup_service "Web UI" "web-ui" 
setup_service "Docker Monitor" "docker-monitor"
setup_service "SSH Manager" "ssh-manager"

# Start just Caddy in Docker
echo "🐳 Starting Caddy container..."
docker-compose -f docker-compose.dev.yml up -d caddy

# Wait for Caddy to be ready
echo "⏳ Waiting for Caddy to start..."
sleep 5

# Check if Caddy is running
if curl -sf http://localhost:2019/config >/dev/null 2>&1; then
    echo "✅ Caddy is running on http://localhost:2019"
else
    echo "❌ Caddy failed to start properly"
fi

echo ""
echo "🎉 DCRP Development Environment Ready!"
echo ""
echo "Next steps:"
echo "1. Start API Server:    cd api-server && source venv/bin/activate && python main.py"
echo "2. Start Web UI:        cd web-ui && source venv/bin/activate && python app.py"
echo "3. Access services:"
echo "   - Main page:         http://localhost"
echo "   - Web UI:            http://localhost:5000"
echo "   - API docs:          http://localhost:8000/docs"
echo "   - Caddy admin:       http://localhost:2019"
echo ""
echo "Optional services (run in separate terminals):"
echo "4. Docker Monitor:      cd docker-monitor && source venv/bin/activate && python monitor.py"
echo "5. SSH Manager:         cd ssh-manager && source venv/bin/activate && python ssh_config.py"