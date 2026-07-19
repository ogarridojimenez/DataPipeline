# --- Build stage ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim
LABEL maintainer="ogarridojimenez"

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy app
WORKDIR /app
COPY etl/ ./etl/
COPY dashboard/ ./dashboard/
COPY pyproject.toml requirements.txt ./

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8501

# Default: run dashboard
CMD ["python", "-m", "etl", "dashboard", "--host", "0.0.0.0"]
