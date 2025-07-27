# Use Debian as a base
FROM python:3.11-slim-bullseye

# Install system dependencies
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    git \
    libsqlite3-0 \
    openssl ssh \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/oglbbs

# Copy project files
COPY . .

# Create virtual environment
RUN python3 -m venv venv \
 && . venv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt

# Expose the SSH port (default 8002)
EXPOSE 8002

# Run BBS on startup
CMD ["sh", "-c", ". venv/bin/activate && python3 -m oglbbs.main -c ./oglbbs.conf"]
