# 001 · ETL Core

**Estado:** propuesta

## Qué hace
Extrae datos de URLs via scraping asíncrono, los limpia y transforma con pandas, y los exporta a SQLite + CSV/JSON.

## Por qué
Fundación del proyecto. Sin ETL no hay datos para el dashboard.

## Requisitos funcionales (EARS)

### Scraping
- CUANDO el usuario ejecuta `python -m etl scrape <url>`, EL SISTEMA DEBE descargar el HTML y extraer datos usando los CSS selectors proporcionados
- CUANDO se scrapean múltiples URLs, EL SISTEMA DEBE respetar rate limit (mín 1s entre requests por dominio)
- CUANDO un request falla, EL SISTEMA DEBE reintentar hasta 3 veces con backoff exponencial
- CUANDO robots.txt bloquea un path, EL SISTEMA DEBE omitir ese path y registrar warning
- CUANDO se completa el scraping, EL SISTEMA DEBE guardar resultados en SQLite

### Procesamiento
- CUANDO el usuario ejecuta `python -m etl process`, EL SISTEMA DEBE limpiar datos: eliminar duplicados, rellenar nulls, normalizar formatos
- CUANDO hay outliers (>3 std dev), EL SISTEMA DEBE marcarlos sin eliminarlos
- CUANDO se completa el procesamiento, EL SISTEMA DEBE exportar a CSV y JSON

### CLI
- CUANDO el usuario ejecuta `python -m etl --help`, EL SISTEMA DEBE mostrar ayuda con subcomandos disponibles
- CUANDO se proporcionan flags inválidos, EL SISTEMA DEBE mostrar error descriptivo

## Requisitos no funcionales
- Throughput: mínimo 10 páginas/segundo en scraping
- Rate limit configurable por CLI flag
- Logs a stderr, datos a stdout/file
- Sin dependencias del sistema (solo pip)

## Criterios de aceptación
- [ ] `python -m etl scrape` extrae datos de una URL de prueba
- [ ] Rate limit funciona (verificable con logs de timestamps)
- [ ] `python -m etl process` limpia datos con nulls/duplicados
- [ ] Export genera SQLite + CSV + JSON válidos
- [ ] `python -m etl --help` muestra ayuda
- [ ] Tests unitarios pasan

## Clarify (edge cases)
| # | Pregunta | Respuesta |
|---|----------|-----------|
| 1 | ¿Timeout de requests? | 30s default, configurable por flag |
| 2 | ¿User-Agent rotatorio? | Sí, lista de 5 UAs, rotación aleatoria |
| 3 | ¿Formato de SQLite? | Una tabla por source URL, schema flexible (JSON columns) |

## Fuera de alcance
- Dashboard (feature 002)
- Docker (feature 003)
- Autenticación/login en targets
- Scraping de JavaScript renderado (solo HTML estático)
