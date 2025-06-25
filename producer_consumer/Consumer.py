# -*- coding: utf-8 -*-
import asyncio
from aiokafka import AIOKafkaConsumer
import asyncpg
import json
import logging
from asyncio_throttle import Throttler
from datetime import datetime 


# Logging
logging.basicConfig(level=logging.INFO)

# Throttler: 2 transaksi per detik
throttler = Throttler(rate_limit=2, period=1)

# Koneksi PostgreSQL (async)
async def connect_postgres():
    while True:
        try:
            conn = await asyncpg.connect(
                host='localhost',
                port=5432,
                user='postgres',
                password='apollo12',
                database='user_logs'
            )
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_activity_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    method TEXT,
                    url TEXT,
                    status_code INT,
                    response_body JSONB,
                    headers JSONB,
                    params JSONB,
                    body TEXT
                );
            ''')
            logging.info("Connected to PostgreSQL and ensured table exists")
            return conn
        except Exception as e:
            logging.error(f"PostgreSQL connection error: {e}")
            await asyncio.sleep(5)

# Kafka consumer setup (async)
async def start_consumer():
    while True:
        try:
            consumer = AIOKafkaConsumer(
                'user-activity-topic',
                bootstrap_servers='localhost:9092',
                group_id='log-consumer-group',
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await consumer.start()
            logging.info("Kafka consumer connected")
            return consumer
        except Exception as e:
            logging.error(f"Kafka connection failed: {e}")
            await asyncio.sleep(5)

# Main loop
async def main():
    conn = await connect_postgres()
    consumer = await start_consumer()

    try:
        async for message in consumer:
            async with throttler:
                log = message.value
                try:
                    await conn.execute('''
                        INSERT INTO user_activity_logs (timestamp, method, url, status_code, response_body, headers, params, body)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ''',
                        datetime.fromisoformat(log.get("timestamp")),
                        log.get("method"),
                        log.get("url"),
                        log.get("status_code"),
                        json.dumps(log.get("response_body")),
                        json.dumps(log.get("headers")),
                        json.dumps(log.get("params")),
                        log.get("body")
                    )
                    logging.info(f"Log saved: {log.get('url')}")
                except Exception as db_err:
                    logging.error(f"DB insert failed: {db_err}")
    finally:
        await consumer.stop()
        await conn.close()

# Run
if __name__ == "__main__":
    asyncio.run(main())
