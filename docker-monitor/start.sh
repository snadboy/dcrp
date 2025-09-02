#!/bin/bash
# Docker Monitor startup script
# Sets up SSH environment and starts monitoring

set -e

echo "Starting Docker Monitor..."

# Set up SSH environment
echo "Setting up SSH environment..."
python3 setup_ssh.py

# Start the monitor
echo "Starting container monitoring..."
exec python3 monitor.py