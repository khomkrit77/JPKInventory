FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/inventory.sqlite3
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && groupadd -g 10001 inventory && useradd -u 10001 -g inventory -M inventory
COPY backend/ ./backend/
COPY index.html ./
COPY src/ ./src/
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=3)" || exit 1
CMD ["gunicorn", "backend.app:create_app()", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp", "--no-control-socket"]
