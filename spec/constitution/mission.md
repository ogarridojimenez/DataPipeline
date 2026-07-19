# Constitución — DataPipeline

## Propósito
Pipeline ETL en Python que extrae datos de internet via scraping, los procesa/limpia y los muestra en un dashboard interactivo. Data engineering puro para CV.

## Para quién
- **Primario:** developer (portfolio CV)
- **Secundario:** cualquier persona que necesite un ETL referencial

## Principios no negociables
1. **Scraping ético:** rate limiting, rotación User-Agent, robots.txt
2. **Modular:** cada fase (scrape/process/visualize/export) es independiente
3. **Reproducible:** Docker + requirements.txt, sin dependencias del sistema
4. **Sin credenciales hardcodeadas:** config por env vars o CLI flags

## Qué NO es
- No es un crawler masivo (miles de URLs)
- No es una app de producción con auth
- No reemplaza a Scrapy/BeautifulSoup (es ligero, httpx + selectolax)

## Glosario
- **ETL:** Extract-Transform-Load
- **Rate limit:** control de frecuencia de requests
- **Selector:** CSS selector para extraer elementos del HTML
