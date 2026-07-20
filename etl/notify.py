"""Notificaciones vía webhook (Slack/Discord) cuando hay nuevos datos."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("etl.notify")

DEFAULT_WEBHOOK_TIMEOUT = 10  # segundos


def send_webhook(
    webhook_url: str,
    message: str,
    fields: dict[str, Any] | None = None,
    timeout: int = DEFAULT_WEBHOOK_TIMEOUT,
) -> bool:
    """Envía un payload genérico a un webhook Slack-compatible.

    Args:
        webhook_url: URL del webhook (Slack / Discord / cualquier webhook que acepte JSON).
        message: Texto principal del mensaje.
        fields: Pares clave/valor para detalles adicionales.
        timeout: Timeout en segundos.

    Returns:
        True si la notificación se envió correctamente.
    """
    payload: dict[str, Any] = {
        "text": message,
    }
    if fields:
        payload["fields"] = [{"title": k, "value": str(v), "short": True} for k, v in fields.items()]

    data = json.dumps(payload).encode("utf-8")
    req = Request(webhook_url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        resp = urlopen(req, timeout=timeout)
        logger.info("Webhook sent: %s", resp.status)
        return True
    except URLError as e:
        logger.warning("Webhook failed: %s", e)
        return False


def notify_scrape_complete(
    webhook_url: str,
    total_urls: int,
    success_count: int,
    total_rows: int,
    skipped: int | None = None,
    db_path: str = "",
) -> bool:
    """Envía resumen de scraping a un webhook."""
    if skipped:
        msg = f"✅ Scraping completado: {success_count}/{total_urls} URLs, {total_rows} filas nuevas ({skipped} duplicados saltados)"
    else:
        msg = f"✅ Scraping completado: {success_count}/{total_urls} URLs, {total_rows} filas guardadas"

    fields = {
        "URLs exitosas": f"{success_count}/{total_urls}",
        "Filas guardadas": str(total_rows),
        "Base de datos": db_path or "N/A",
    }
    if skipped:
        fields["Duplicados saltados"] = str(skipped)

    return send_webhook(webhook_url, msg, fields)
