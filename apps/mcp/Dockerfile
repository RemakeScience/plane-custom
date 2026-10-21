FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PLANE_BASE_URL=http://api:8000

WORKDIR /app

COPY pyproject.toml README.md ./
COPY plane_fork_mcp ./plane_fork_mcp
RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 mcp

USER mcp
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

ENTRYPOINT ["python", "-m", "plane_fork_mcp"]
CMD ["http"]
