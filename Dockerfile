FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg build-essential git \
 && rm -rf /var/lib/apt/lists/*

# Install NodeJS 20 (NodeSource) and Mux CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y nodejs \
 && npm install -g @mux/cli \
 && rm -rf /var/lib/apt/lists/* /root/.npm

# Copy requirements and install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project
COPY . /app

# Create runtime directories
RUN mkdir -p /app/generated_videos /app/generated_scripts

# Entrypoint helper
COPY docker_entrypoint.sh /app/docker_entrypoint.sh
RUN chmod +x /app/docker_entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/docker_entrypoint.sh"]
CMD ["python","run.py","--mode","complete"]
