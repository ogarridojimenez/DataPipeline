"""Tests para webhook notification."""

import http.server
import json
import threading
import time

import pytest

from etl.notify import notify_scrape_complete, send_webhook


@pytest.fixture
def webhook_server():
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            received.append(json.loads(body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", received
    server.server_close()


class TestWebhook:
    def test_send_webhook(self, webhook_server):
        url, received = webhook_server
        ok = send_webhook(url, "test msg", {"key": "val"})
        time.sleep(0.1)
        assert ok is True
        assert len(received) == 1
        assert received[0]["text"] == "test msg"

    def test_notify_scrape_complete(self, webhook_server):
        url, received = webhook_server
        notify_scrape_complete(url, total_urls=5, success_count=4, total_rows=10, skipped=2, db_path="/tmp/test.db")
        time.sleep(0.1)
        assert len(received) == 1
        assert "Scraping completado" in received[0]["text"]
        assert received[0]["text"] == "✅ Scraping completado: 4/5 URLs, 10 filas nuevas (2 duplicados saltados)"
        fields = {f["title"]: f["value"] for f in received[0]["fields"]}
        assert fields["URLs exitosas"] == "4/5"
        assert fields["Filas guardadas"] == "10"
        assert fields["Duplicados saltados"] == "2"

    def test_invalid_url_returns_false(self):
        ok = send_webhook("http://localhost:1/nonexistent", "test", {})
        assert ok is False
