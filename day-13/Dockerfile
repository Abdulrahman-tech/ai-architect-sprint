# Dockerfile — Day 13: DevOps AutoPilot containerisation
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (better Docker layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Never run as root in production
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Environment variables (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import os; assert os.getenv('GOOGLE_API_KEY'), 'API key missing'" || exit 1

# Run the agent
CMD ["python", "agent.py"]