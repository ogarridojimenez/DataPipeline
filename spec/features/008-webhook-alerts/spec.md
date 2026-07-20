# 008 · Webhook Alerts

**Estado:** implementado ✅

## Objetivo
Notificar scraping completado vía Slack/Discord webhook.

## RF (EARS)
- CUANDO `run_scrape` finaliza CON webhook configurado, EL SISTEMA DEBE enviar POST con resumen
- CUANDO webhook_url NO está configurado, EL SISTEMA DEBE omitir notificación
- CUANDO el webhook falla (timeout/error), EL SISTEMA DEBE loguear warning y continuar

## CLI
```
python -m etl scrape --webhook https://hooks.slack.com/... ...
```
