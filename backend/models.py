from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base
import uuid

def new_id():
    return "WTR-" + str(uuid.uuid4())[:4].upper()

class Booking(Base):
    __tablename__ = "bookings"

    id          = Column(String, primary_key=True, default=new_id)
    name        = Column(String, nullable=False)
    phone       = Column(String, nullable=False)
    ward        = Column(String, nullable=False)
    address     = Column(String, nullable=False)
    size_litres = Column(Integer, nullable=False)   # 500, 1000, 2000, 5000
    priority    = Column(String, default="normal")  # "normal" or "high"
    status      = Column(String, default="pending") # pending → assigned → delivered
    tanker_id   = Column(String, nullable=True)
    eta_minutes = Column(Integer, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

class Tanker(Base):
    __tablename__ = "tankers"

    id          = Column(String, primary_key=True)  # "TK-01"
    driver_name = Column(String, nullable=False)
    capacity    = Column(Integer, default=5000)
    fill_pct    = Column(Integer, default=100)
    status      = Column(String, default="idle")    # idle, active, busy
    ward        = Column(String, nullable=True)
    active      = Column(Boolean, default=True)

class GpsPing(Base):
    __tablename__ = "gps_pings"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    tanker_id  = Column(String, nullable=False)
    lat        = Column(String, nullable=False)  # latitude
    lng        = Column(String, nullable=False)  # longitude
    recorded_at = Column(DateTime, server_default=func.now())