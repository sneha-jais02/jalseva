from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from database import engine, Base
from routes import router, latest_positions
from algorithm import run_dispatch
import models

# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JalSeva API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

# ── Auto-dispatch scheduler ───────────────────────────────────────
# Runs run_dispatch() every 30 seconds in the background
scheduler = BackgroundScheduler()
scheduler.add_job(
    func     = lambda: run_dispatch(latest_positions),
    trigger  = "interval",
    seconds  = 30,
    id       = "auto_dispatch",
    max_instances = 1  # never run two at the same time
)
scheduler.start()
print("Auto-dispatch scheduler started — running every 30 seconds")

# Shut down scheduler cleanly when server stops
@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()