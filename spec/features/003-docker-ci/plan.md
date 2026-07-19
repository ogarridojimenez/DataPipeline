# Plan — Feature 003: Docker + CI

## Dockerfile
```dockerfile
FROM python:3.11-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . /app
WORKDIR /app
CMD ["python", "-m", "etl", "dashboard"]
```

## docker-compose.yml
- Service: `app` (build + ports)
- Volume: `./data` para persistir SQLite

## GitHub Actions CI
- Trigger: push, pull_request
- Steps: checkout → python setup → pip install → pytest

## GitHub Actions Schedule
- Cron: `0 6 * * 1` (lunes 6am)
- Steps: checkout → pip install → scrape sample URLs → commit data
