"""
Database Schemas for Smart Indoor Air Quality Monitoring

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Device(BaseModel):
    device_id: str = Field(..., description="Unique ID of the embedded device")
    name: Optional[str] = Field(None, description="Friendly name")
    location: Optional[str] = Field(None, description="Room or area")
    power: bool = Field(True, description="Purifier power state")
    mode: Literal["auto", "manual"] = Field("auto", description="Control mode")
    fan_speed: int = Field(1, ge=0, le=5, description="Fan speed level 0-5")
    last_seen: Optional[datetime] = Field(None, description="Last heartbeat timestamp")

class SensorReading(BaseModel):
    device_id: str = Field(..., description="Source device ID")
    pm2_5: float = Field(..., ge=0, description="PM2.5 ug/m3")
    pm10: float = Field(..., ge=0, description="PM10 ug/m3")
    co2: Optional[float] = Field(None, ge=0, description="CO2 ppm")
    tvoc: Optional[float] = Field(None, ge=0, description="Total VOC ppb")
    temperature: Optional[float] = Field(None, description="Celsius")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Relative humidity %")
    aqi: Optional[int] = Field(None, ge=0, le=500, description="Calculated AQI (approx)")
    timestamp: Optional[datetime] = Field(None, description="Reading time")

class Thresholds(BaseModel):
    device_id: Optional[str] = Field(None, description="If set, thresholds scoped to a device")
    pm2_5_good: float = Field(12.0, ge=0)
    pm2_5_moderate: float = Field(35.4, ge=0)
    pm10_good: float = Field(54.0, ge=0)
    co2_max: float = Field(1200.0, ge=0)
    tvoc_max: float = Field(500.0, ge=0)

class DeviceCommand(BaseModel):
    device_id: str
    power: Optional[bool] = None
    mode: Optional[Literal["auto", "manual"]] = None
    fan_speed: Optional[int] = Field(None, ge=0, le=5)
