# Spec — Feature 003: Docker + GitHub Actions CI

## Objetivo
Containerizar la app y configurar CI/CD automatizado.

## Requisitos

### Docker
- Dockerfile multi-stage (build + runtime)
- docker-compose.yml para desarrollo
- Imagen <200MB (python:3.11-slim)

### GitHub Actions
- CI: test on push/PR
- Scheduled: scraping semanal (cron)
- Publish: push imagen a GHCR

## Archivos
- `Dockerfile`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/schedule.yml`
