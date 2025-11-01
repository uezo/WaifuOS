FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working dir
WORKDIR /app

# Copy application
COPY --chown=app:app ./speech-gateway/ /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Switch to non-root user
USER app

EXPOSE 8000
