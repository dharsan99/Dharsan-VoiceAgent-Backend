# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python application
COPY requirements.txt .
COPY main.py .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create models directory
RUN mkdir -p /models

# Create non-root user
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app /models

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"] 