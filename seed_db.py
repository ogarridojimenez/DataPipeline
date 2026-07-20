"""Seed test database with sample data for dashboard demo."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

db_path = Path("E:/Mis proyectos/DataPipeline/data/pipeline.db")
db_path.parent.mkdir(exist_ok=True)
conn = sqlite3.connect(str(db_path))

conn.execute("""CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT, source_domain TEXT, data TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS processed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT, source_domain TEXT, data TEXT
)""")

count = conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
if count > 0:
    print(f"DB ya tiene {count} registros")
    conn.close()
    exit(0)

items = [
    (
        "http://listado.mercadolibre.com.mx/laptop",
        "mercadolibre.com",
        [
            {"title": "Laptop HP Pavilion 15", "price": "$12,999", "category": "Laptops"},
            {"title": "Laptop Dell Inspiron 14", "price": "$15,499", "category": "Laptops"},
            {"title": "Laptop Lenovo IdeaPad 3", "price": "$9,899", "category": "Laptops"},
            {"title": "Laptop ASUS VivoBook 15", "price": "$11,299", "category": "Laptops"},
        ],
    ),
    (
        "http://listado.mercadolibre.com.mx/audifonos",
        "mercadolibre.com",
        [
            {"title": "Audifonos Sony WH-1000XM5", "price": "$5,999", "category": "Audio"},
            {"title": "Audifonos JBL Tune 770NC", "price": "$1,899", "category": "Audio"},
            {"title": "Audifonos Apple AirPods Pro 2", "price": "$4,499", "category": "Audio"},
        ],
    ),
    (
        "http://listado.mercadolibre.com.mx/monitores",
        "mercadolibre.com",
        [
            {"title": "Monitor LG UltraGear 27", "price": "$4,299", "category": "Monitores"},
            {"title": "Monitor Samsung 24 FHD", "price": "$2,899", "category": "Monitores"},
            {"title": "Monitor Dell 27 4K", "price": "$6,799", "category": "Monitores"},
        ],
    ),
    (
        "https://www.amazon.com.mx/electronics",
        "amazon.com.mx",
        [
            {"title": "Mouse Logitech MX Master 3S", "price": "$1,599", "category": "Accesorios"},
            {"title": "Teclado Mecanico Keychron K2", "price": "$2,199", "category": "Accesorios"},
            {"title": "Webcam Logitech C920", "price": "$899", "category": "Accesorios"},
        ],
    ),
    (
        "https://www.amazon.com.mx/celulares",
        "amazon.com.mx",
        [
            {"title": "Samsung Galaxy S24 Ultra", "price": "$24,999", "category": "Celulares"},
            {"title": "iPhone 15 Pro Max", "price": "$29,999", "category": "Celulares"},
        ],
    ),
    (
        "https://www.falabella.com.mx/tecnologia",
        "falabella.com.mx",
        [
            {"title": "iPad Air M2", "price": "$13,499", "category": "Tablets"},
            {"title": "MacBook Air M3", "price": "$22,999", "category": "Laptops"},
            {"title": "Apple Watch Series 9", "price": "$7,999", "category": "Wearables"},
        ],
    ),
]

now = datetime.now()
for url, domain, data_list in items:
    for i, d in enumerate(data_list):
        t = now - timedelta(days=i % 3, hours=i * 2)
        conn.execute(
            "INSERT INTO raw_data (source_url, source_domain, data, scraped_at) VALUES (?,?,?,?)",
            (url, domain, json.dumps(data_list), t.isoformat()),
        )

for url, domain, data_list in items[:3]:
    for item in data_list:
        conn.execute(
            "INSERT INTO processed_data (source_url, source_domain, data) VALUES (?,?,?)",
            (url, domain, json.dumps(item)),
        )

conn.commit()
total = conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
print(f"DB lista: {total} registros en {db_path}")
conn.close()
