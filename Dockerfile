# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    AGENT_CONFIG=/app/agent.json

WORKDIR /app

# git: allow pinned git dependencies in requirements.mcp.txt
# node/npm/npx: support common stdio MCP servers (for example @modelcontextprotocol/*)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.mcp.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip install -r requirements.mcp.txt

COPY agent.json agent.gemini.json agent.yaml ./
COPY skills ./skills
COPY src ./src

RUN mkdir -p /app/.agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "agentfw.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
