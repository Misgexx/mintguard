# syntax=docker/dockerfile:1
FROM python:3.13-slim

# System deps (build tools for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[dev]"

# Copy the app code
COPY app /app/app

# Container runtime env
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000

# Start API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
