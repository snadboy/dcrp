# DCRP API Server - Simple Dockerfile without curl
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including SSH client
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create non-root user (commented out for log file access)
# RUN groupadd -r apiuser && useradd -r -g apiuser apiuser && \
#     chown -R apiuser:apiuser /app
# USER apiuser

# Expose port
EXPOSE 8000

# Health check using Python instead of curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python", "main.py"]