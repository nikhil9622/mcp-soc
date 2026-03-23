# Multi-stage build for smaller production images
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/home/mcpsoc/.local/bin:$PATH

# Copy application code
COPY agents/ ./agents/
COPY api/ ./api/
COPY config/ ./config/
COPY db/ ./db/
COPY detection_rules/ ./detection_rules/
COPY shared/ ./shared/
COPY email_templates/ ./email_templates/
COPY main.py .

# Create non-root user, move packages to user home, fix ownership
RUN useradd -m -u 1000 mcpsoc \
    && cp -r /root/.local /home/mcpsoc/.local \
    && chown -R mcpsoc:mcpsoc /app \
    && chown -R mcpsoc:mcpsoc /home/mcpsoc/.local
USER mcpsoc

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# CMD is overridden per service in docker-compose.yml
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
