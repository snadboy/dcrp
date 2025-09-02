# DCRP Docker Monitor with SSH Environment
FROM python:3.11-slim

# Install system dependencies (matching docker-revp)
RUN apt-get update && apt-get install -y \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI
RUN apt-get update && apt-get install -y \
    ca-certificates \
    gnupg \
    lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY monitor.py setup_ssh.py start.sh ./

# Create non-root user with home directory for SSH config
RUN groupadd -r monitor && useradd -r -g monitor monitor -m -d /home/monitor && \
    mkdir -p /home/monitor/.ssh && \
    chown -R monitor:monitor /app /home/monitor && \
    chmod 700 /home/monitor/.ssh && \
    chmod +x start.sh
USER monitor

# Run the application with SSH setup
CMD ["./start.sh"]