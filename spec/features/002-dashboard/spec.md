# Spec — Feature 002: Dashboard

## Objetivo
Dashboard web interactivo que visualiza datos procesados del pipeline ETL.

## Stack (disponible)
- Starlette 1.0.1 + uvicorn 0.41.0 (ASGI)
- Jinja2 3.1.6 (templates)
- Chart.js (CDN, client-side)
- SQLite (data source)

## Actores
- **Usuario**: visualiza datos, filtra, exporta

## Requisitos funcionales (EARS)

- CUANDO el usuario accede a `/`, EL SISTEMA DEBE mostrar dashboard con gráficos y stats
- CUANDO el usuario accede a `/api/stats`, EL SISTEMA DEBE retornar estadísticas resumen (JSON)
- CUANDO el usuario accede a `/api/top`, EL SISTEMA DEBE retornar top N items por frecuencia
- CUANDO el usuario filtra por dominio/fecha, EL SISTEMA DEBE filtrar los datos mostrados
- CUANDO el usuario solicita exportar, EL SISTEMA DEBE generar CSV/JSON descargable

## Requisitos no funcionales
- Dashboard carga en <2s con 10k registros
- Responsive (mobile-friendly)

## Non-goals
- Autenticación
- Real-time updates (WebSocket)
- Streamlit (no disponible)

## Criterios de aceptación
- Dashboard muestra gráficos de barras + línea temporales
- Stats: total registros, dominios, fechas
- Export funciona desde el browser
