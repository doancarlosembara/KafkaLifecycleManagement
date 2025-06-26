from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from kafka import KafkaProducer
from datetime import datetime
import json
import logging
import httpx
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Inisialisasi FastAPI & logging
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Kafka setup
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
    retries=0,
    request_timeout_ms=3000,
    max_block_ms=3000
)

executor = ThreadPoolExecutor(max_workers=1)

# CIAM URL tujuan
CIAM_URL = "https://dev-1-aws.ciam.telkomsel.com/iam/v1/realms/tsel/authenticate?authIndexType=service&authIndexValue=phoneLogin"

# Fungsi untuk kirim log ke Kafka secara async
async def send_to_kafka(data: dict):
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(executor, lambda: producer.send("user-activity-topic", data).get(timeout=3))
        logging.info("✅ Log sent to Kafka")
        return True
    except Exception as e:
        logging.error(f"❌ Kafka send failed: {e}")
        return False

# Endpoint utama proxy logger
@app.api_route("/send-log", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_request(request: Request):
    method = request.method
    headers = dict(request.headers)
    body = await request.body() if method in ["POST", "PUT", "PATCH"] else None

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.request(
                method=method,
                url=CIAM_URL,
                headers=headers,
                content=body
            )
    except Exception as e:
        logging.error(f"❌ CIAM request failed: {e}")
        return JSONResponse(status_code=500, content={"error": f"❌ CIAM request failed: {e}"})

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    # Data log yang akan dikirim ke Kafka
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "method": method,
        "url": CIAM_URL,
        "status_code": response.status_code,
        "response_body": response_body,
        "headers": headers,
        "params": dict(request.query_params),
        "body": body.decode() if body else None,
        "client_ip": request.client.host,
        "full_path": str(request.url)
    }

    success = await send_to_kafka(log_data)

    return {
        "status": "success" if success else "failed",
        "forwarded_to": CIAM_URL,
        "response": response_body,
        "log": log_data if success else "Kafka failed"
    }