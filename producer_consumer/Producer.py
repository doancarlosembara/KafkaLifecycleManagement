from fastapi import FastAPI, Request, Path
from pydantic import BaseModel
import httpx
from fastapi.responses import JSONResponse
import json
from datetime import datetime
import logging
import asyncio

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# 👉 Replace with actual bastion IP/domain
BASTION_FLASK_API = "http://connect:5000/submit"

# Send log to Bastion Flask Kafka Producer
async def send_to_bastion(data: dict):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(BASTION_FLASK_API, json=data)
            if response.status_code == 200:
                logging.info("✅ Log sent to Kafka via Bastion")
                return True
            else:
                logging.error(f"❌ Bastion responded with error {response.status_code}: {response.text}")
                return False
    except Exception as e:
        logging.error(f"❌ Failed to reach Bastion: {e}")
        return False

@app.api_route("/send-log", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def send_log(request: Request):
    url = 'https://dev-1-aws.ciam.telkomsel.com/iam/v1/realms/tsel/authenticate?authIndexType=service&authIndexValue=phoneLogin'
    headers = {'Content-Type': 'application/json'}
    method = request.method
    body = await request.body() if method in ["POST", "PUT", "PATCH"] else None

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"❌ Request failed: {e}"})

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    log_data = {
        "timestamp": datetime.utcnow(),
        "method": method,
        "url": url,
        "status_code": response.status_code,
        "response_body": response_body,
        "headers": dict(response.request.headers),
        "params": dict(request.query_params),
        "body": body.decode() if body else None
    }

    success = await send_to_bastion(log_data)
    if success:
        return {"status": "success", "data": log_data}
    else:
        return JSONResponse(status_code=500, content={"error": "❌ Failed to forward log to Kafka"})

class UserUpdate(BaseModel):
    name: str
    job: str

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

@app.put("/user/{user_id}")
async def update_user(user_id: int, payload: UserUpdate):
    url = f'https://reqres.in/api/users/{user_id}'
    headers = {'Content-Type': 'application/json'}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=payload.dict())
    except Exception as e:
        return {"error": f"❌ Update failed: {e}"}

    try:
        response_body = response.json()
    except Exception:
        response_body = response.text

    log_data = {
        "timestamp": datetime.utcnow(),
        "method": "PUT",
        "url": url,
        "status_code": response.status_code,
        "response_body": response_body,
        "headers": dict(response.request.headers),
        "params": {},
        "body": json.dumps(payload.dict())
    }

    success = await send_to_bastion(log_data)
    if success:
        return {"status": "success", "data": response_body}
    else:
        return {"error": "❌ Kafka log failed"}
