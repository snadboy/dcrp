# DCRP Web UI - Simple Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Create non-root user
RUN groupadd -r webuser && useradd -r -g webuser webuser && \
    chown -R webuser:webuser /app
USER webuser

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]