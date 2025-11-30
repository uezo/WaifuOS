FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working dir
WORKDIR /app

# Copy application
COPY --chown=app:app ./server/sbv2lite/ /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Install ffmpeg
RUN curl -s -L -o ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
RUN mkdir ffmpeg
RUN tar -xJf ffmpeg.tar.xz --strip-components=1 -C ffmpeg
RUN rm ffmpeg.tar.xz

# Allow non-root user to update venv-installed packages (e.g. pyopenjtalk dictionary)
RUN chown -R app:app /opt/venv

# Switch to non-root user
USER app

EXPOSE 8000
