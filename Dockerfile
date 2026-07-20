# Build stage — instala dependencias
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install ".[dashboard]"

# Runtime stage — imagen final ligera
FROM python:3.11-slim

# Instalar solo runtime OS deps necesarios
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN groupadd -r etl && useradd -r -g etl -d /app -s /bin/false etl

WORKDIR /app

# Copiar dependencias desde builder
COPY --from=builder /install /usr/local

# Copiar código de la aplicación
COPY etl/ etl/
COPY dashboard/ dashboard/

# Volumen para datos persistentes
VOLUME /app/data

EXPOSE 8501

# Usar usuario no-root
USER etl

ENTRYPOINT ["python", "-m", "etl"]
CMD ["dashboard", "--mode", "streamlit", "--host", "0.0.0.0", "--port", "8501"]
