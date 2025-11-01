FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    portaudio19-dev \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY ./aiavatar/requirements.txt /tmp/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Set working dir
WORKDIR /app

# Switch to non-root user
USER app

EXPOSE 8000
