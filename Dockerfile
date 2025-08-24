# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install runtime deps (if any OS packages are needed later, add them here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Create app user and data directory
RUN useradd -m -u 10001 appuser \
  && mkdir -p /data /data/logs \
  && chown -R appuser:appuser /app /data

USER appuser

# Default runtime environment (can be overridden by env or compose)
ENV BASE_DIR=/data \
    LOG_FILE=/data/logs/bot.log \
    LOG_LEVEL=INFO

# No port exposure needed (bot uses outbound HTTP)

CMD ["python", "main.py"]
