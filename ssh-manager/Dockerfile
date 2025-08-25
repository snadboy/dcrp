# DCRP SSH Manager - Simple Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ssh_config.py .

# Create SSH directory and set permissions
RUN mkdir -p /app/ssh-keys && \
    chmod 700 /app/ssh-keys

# Create non-root user
RUN groupadd -r sshuser && useradd -r -g sshuser sshuser && \
    chown -R sshuser:sshuser /app
USER sshuser

# Run the application
CMD ["python", "ssh_config.py"]