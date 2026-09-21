FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the web service needs (mcp_server.py is stdio-local, not deployed).
COPY server.py core.py verify_onchain.py ./
COPY configs/ ./configs/
# receipts/ is created at runtime by log_receipt()

EXPOSE 8000

# Render/Railway/Fly inject $PORT; default 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
