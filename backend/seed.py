from database import SessionLocal, engine, Base
from models import Tanker
import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

tankers = [
    Tanker(id="TK-01", driver_name="Ramesh K.",  capacity=5000, fill_pct=85, ward="A"),
    Tanker(id="TK-02", driver_name="Sunil M.",   capacity=3000, fill_pct=60, ward="B"),
    Tanker(id="TK-03", driver_name="Dinesh P.",  capacity=5000, fill_pct=90, ward="B"),
    Tanker(id="TK-04", driver_name="Vijay R.",   capacity=2000, fill_pct=40, ward="C"),
    Tanker(id="TK-05", driver_name="Anand S.",   capacity=5000, fill_pct=100, ward="D"),
]

for t in tankers:
    db.merge(t)  # merge = insert if not exists, update if exists

db.commit()
print("Tankers added successfully!")
db.close()