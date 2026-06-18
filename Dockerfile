FROM python:3.12-slim

WORKDIR /app

# ---- System dependencies ----
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    libreoffice-impress \
    libreoffice-writer \
    fonts-noto-cjk \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Node.js (for pptx skill's PptxGenJS) ----
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm config set registry https://registry.npmmirror.com \
    && npm install -g pptxgenjs

# ---- Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# ---- Application code ----
COPY server.py .
COPY agent.md .
COPY skills/ ./skills/

EXPOSE 8046

# ---- Runtime settings (overridable via env) ----
ENV HOST="0.0.0.0"
ENV PORT="8046"
ENV WORKERS=${WORKERS:-0}
ENV TIMEOUT="600"
ENV GRACEFUL_TIMEOUT="30"
ENV KEEP_ALIVE="75"
ENV WORKER_CONNECTIONS="1000"
ENV BACKLOG="2048"
ENV MAX_REQUESTS="10000"
ENV MAX_REQUESTS_JITTER="1000"

# ---- Health check ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8046/health')" || exit 1

CMD ["sh", "-c", "gunicorn server:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind ${HOST}:${PORT} \
    --workers ${WORKERS} \
    --timeout ${TIMEOUT} \
    --graceful-timeout ${GRACEFUL_TIMEOUT} \
    --keep-alive ${KEEP_ALIVE} \
    --worker-connections ${WORKER_CONNECTIONS} \
    --backlog ${BACKLOG} \
    --max-requests ${MAX_REQUESTS} \
    --max-requests-jitter ${MAX_REQUESTS_JITTER} \
    --access-logfile - \
    --error-logfile -"]
