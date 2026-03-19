from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Booking, Tanker, GpsPing
import random, string

router = APIRouter()

# ── What data the booking form sends ──────────────────────────────
class BookingRequest(BaseModel):
    name:        str
    phone:       str
    ward:        str
    address:     str
    size_litres: int
    priority:    Optional[str] = "normal"

# ── POST /bookings — resident submits a booking ───────────────────
@router.post("/bookings")
def create_booking(data: BookingRequest, db: Session = Depends(get_db)):
    # Generate a booking ID like WTR-A3F1
    booking_id = "WTR-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    booking = Booking(
        id          = booking_id,
        name        = data.name,
        phone       = data.phone,
        ward        = data.ward,
        address     = data.address,
        size_litres = data.size_litres,
        priority    = data.priority,
        status      = "pending",
        eta_minutes = random.randint(15, 45)  # real ETA logic comes in Phase 3
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"booking_id": booking.id, "eta_minutes": booking.eta_minutes, "status": "pending"}

# ── GET /bookings — admin sees all bookings ───────────────────────
@router.get("/bookings")
def list_bookings(db: Session = Depends(get_db)):
    bookings = db.query(Booking).order_by(Booking.created_at.desc()).all()
    return bookings

# ── GET /bookings/{id} — resident tracks their booking ───────────
@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

# ── PATCH /bookings/{id}/assign — admin assigns a tanker ─────────
@router.patch("/bookings/{booking_id}/assign")
def assign_tanker(booking_id: str, tanker_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.tanker_id = tanker_id
    booking.status    = "assigned"
    db.commit()
    return {"message": f"Tanker {tanker_id} assigned to {booking_id}"}

# ── GET /tankers — list all tankers ──────────────────────────────
@router.get("/tankers")
def list_tankers(db: Session = Depends(get_db)):
    return db.query(Tanker).filter(Tanker.active == True).all()

# ── PATCH /bookings/{id}/deliver — mark as delivered ─────────────
@router.patch("/bookings/{booking_id}/deliver")
def mark_delivered(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = "delivered"
    db.commit()
    return {"message": f"{booking_id} marked as delivered"}

# ── In-memory store for the LATEST position of each tanker ───────
# This means we can get any tanker's current location instantly
# without hitting the database every time
latest_positions = {}

class GpsUpdate(BaseModel):
    tanker_id: str
    lat:       float
    lng:       float

# ── POST /location — driver's phone calls this every 10 seconds ──
@router.post("/location")
def update_location(data: GpsUpdate, db: Session = Depends(get_db)):
    # 1. Save to in-memory dict (for instant live map reads)
    latest_positions[data.tanker_id] = {
        "tanker_id": data.tanker_id,
        "lat":       data.lat,
        "lng":       data.lng,
    }
    # 2. Also save to database (for route history later)
    ping = GpsPing(
        tanker_id = data.tanker_id,
        lat       = str(data.lat),
        lng       = str(data.lng),
    )
    db.add(ping)
    db.commit()
    return {"status": "ok"}

# ── GET /locations — admin map calls this to get all tanker spots ─
@router.get("/locations")
def get_locations():
    return list(latest_positions.values())

# ── GET /locations/{tanker_id} — get one tanker's current spot ───
@router.get("/locations/{tanker_id}")
def get_tanker_location(tanker_id: str):
    pos = latest_positions.get(tanker_id)
    if not pos:
        raise HTTPException(status_code=404, detail="No location data yet")
    return pos