import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Device, SensorReading, Thresholds, DeviceCommand

app = FastAPI(title="Smart Indoor Air Quality Monitoring & Purification API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Smart IAQ backend running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Utility

def compute_aqi(pm25: Optional[float], pm10: Optional[float]) -> Optional[int]:
    if pm25 is None and pm10 is None:
        return None
    # Simple heuristic (not official): normalize to 500 scale
    aqi_pm25 = min(max((pm25 or 0) * 5, 0), 500)
    aqi_pm10 = min(max((pm10 or 0) * 2, 0), 500)
    return int(max(aqi_pm25, aqi_pm10))

# Ingestion endpoint for embedded devices

@app.post("/api/readings")
def ingest_reading(payload: SensorReading):
    data = payload.model_dump()
    if data.get("timestamp") is None:
        data["timestamp"] = datetime.now(timezone.utc)
    if data.get("aqi") is None:
        data["aqi"] = compute_aqi(data.get("pm2_5"), data.get("pm10"))

    # Ensure device exists/heartbeat update
    device_filter = {"device_id": data["device_id"]}
    existing = list(db["device"].find(device_filter)) if db else []
    if existing:
        db["device"].update_one(device_filter, {"$set": {"last_seen": datetime.now(timezone.utc)}})
    else:
        create_document("device", Device(device_id=data["device_id"]).model_dump())

    inserted_id = create_document("sensorreading", data)
    return {"status": "ok", "id": inserted_id}

# Query latest readings (dashboard)

class LatestQuery(BaseModel):
    device_id: Optional[str] = None
    limit: int = 50

@app.get("/api/readings/latest")
def get_latest_readings(device_id: Optional[str] = None, limit: int = 50):
    query: Dict[str, Any] = {}
    if device_id:
        query["device_id"] = device_id
    docs = db["sensorreading"].find(query).sort("timestamp", -1).limit(limit)
    return [{**{k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in d.items()}, "_id": str(d.get("_id"))} for d in docs]

# Devices list

@app.get("/api/devices")
def list_devices():
    devices = get_documents("device")
    return [{**d, "_id": str(d.get("_id"))} for d in devices]

# Thresholds management (one doc; optionally per device)

@app.post("/api/thresholds")
def set_thresholds(th: Thresholds):
    scope = {"device_id": th.device_id} if th.device_id else {"device_id": {"$exists": False}}
    db["thresholds"].update_one(scope, {"$set": th.model_dump()}, upsert=True)
    return {"status": "ok"}

@app.get("/api/thresholds")
def get_thresholds(device_id: Optional[str] = None):
    scope = {"device_id": device_id} if device_id else {"device_id": {"$exists": False}}
    doc = db["thresholds"].find_one(scope)
    if not doc:
        return Thresholds(device_id=device_id).model_dump()
    doc["_id"] = str(doc["_id"]) if "_id" in doc else None
    return doc

# Commands for devices (devices can poll this)

@app.post("/api/commands")
def push_command(cmd: DeviceCommand):
    cmd_doc = cmd.model_dump(exclude_none=True)
    cmd_doc["created_at"] = datetime.now(timezone.utc)
    inserted_id = create_document("devicecommand", cmd_doc)
    return {"status": "queued", "id": inserted_id}

@app.get("/api/commands/next")
def next_command(device_id: str):
    doc = db["devicecommand"].find_one({"device_id": device_id}, sort=[("created_at", 1)])
    if not doc:
        return {"command": None}
    db["devicecommand"].delete_one({"_id": doc["_id"]})
    doc["_id"] = str(doc["_id"]) if "_id" in doc else None
    return {"command": doc}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
