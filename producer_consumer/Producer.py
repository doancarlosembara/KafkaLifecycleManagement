"""import requests
from kafka import KafkaProducer
import json
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

url = 'https://reqres.in/api/users/2'
headers = {
    'Content-Type': 'application/json'
}
response = requests.get(url, headers=headers)

log_data = {
    "timestamp": datetime.utcnow().isoformat(),
    "method": "GET",
    "url": url,
    "status_code": response.status_code,
    "response_body": response.json(),
    "headers": dict(response.request.headers),
    "params": {},
    "body": None
}

# Kirim ke Kafka
producer.send("user-activity-topic", log_data)
producer.flush()
print("✅ Log sent to Kafka")
"""
from fastapi import FastAPI, Request, Path
from pydantic import BaseModel
import httpx
import json
from datetime import datetime
import logging
import asyncio
from kafka import KafkaProducer
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ✅ ThreadPool untuk Kafka
executor = ThreadPoolExecutor(max_workers=1)

# ✅ Inisialisasi Kafka producer
def create_producer():
    return KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
        request_timeout_ms=3000,
        retries=0,
        max_block_ms=3000
    )

producer = create_producer()

# ✅ Fungsi kirim ke Kafka
async def send_to_kafka(data: dict):
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(executor, lambda: producer.send("user-activity-topic", data).get(timeout=3))
        logging.info("✅ Log sent to Kafka")
        return True
    except Exception as e:
        logging.error(f"❌ Kafka send failed: {e}")
        return False

# ✅ Endpoint fleksibel (GET, POST, PUT, PATCH, DELETE)
@app.api_route("/send-log", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def send_log(request: Request):
    url = 'https://reqres.in/api/users/2'
    headers = {'Content-Type': 'application/json'}
    method = request.method
    body = await request.body()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body if method in ["POST", "PUT", "PATCH"] else None
            )
    except Exception as e:
        return {"error": f"❌ Request failed: {e}"}

    log_data = {
        "timestamp": datetime.utcnow(),
        "method": method,
        "url": url,
        "status_code": response.status_code,
        "response_body": response.json(),
        "headers": dict(response.request.headers),
        "params": dict(request.query_params),
        "body": body.decode() if body else None
    }

    success = await send_to_kafka(log_data)
    if success:
        return {"status": "success", "data": log_data}
    else:
        return {"error": "❌ Kafka producer not available or send failed"}

# ✅ Model untuk update user
class UserUpdate(BaseModel):
    name: str
    job: str

# ✅ Endpoint GET user by ID
@app.get("/user/{user_id}")
async def get_user(user_id: int = Path(..., description="ID user dari Reqres")):
    url = f'https://reqres.in/api/users/{user_id}'

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        return {
            "status_code": response.status_code,
            "data": response.json()
        }
    except Exception as e:
        return {"error": f"❌ Failed to fetch user: {e}"}

# ✅ Endpoint PUT update user & log ke Kafka
@app.put("/user/{user_id}")
async def update_user(user_id: int, payload: UserUpdate):
    url = f'https://reqres.in/api/users/{user_id}'
    headers = {'Content-Type': 'application/json'}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=payload.dict())
    except Exception as e:
        return {"error": f"❌ Update failed: {e}"}

    log_data = {
        "timestamp": datetime.utcnow(),
        "method": "PUT",
        "url": url,
        "status_code": response.status_code,
        "response_body": response.json(),
        "headers": dict(response.request.headers),
        "params": {},
        "body": json.dumps(payload.dict())
    }

    success = await send_to_kafka(log_data)
    if success:
        return {"status": "success", "data": response.json()}
    else:
        return {"error": "❌ Kafka log failed"}
