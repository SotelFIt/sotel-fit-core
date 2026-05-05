import logging
import sys
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

from core.database import Base, engine
from routers import landbot, clients, auth
from routers.admin import router as admin_router
from routers.cron import router as cron_router
from routers.twilio_webhook import router as twilio_router
from routers.stripe_webhook import router as stripe_router
from routers.lead_onboarding import router as lead_onboarding_router
from models import *  # noqa

logger.info("Importando routers...")

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Banco de dados inicializado")
except Exception as e:
    logger.warning(f"Banco de dados nao disponivel: {e}")

from sqlalchemy import text
with engine.connect() as conn:
    migrations = [
        "ALTER TABLE conversation_states ADD COLUMN IF NOT EXISTS onboarding_link_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS objective VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'lead'",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS age INTEGER",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS weight FLOAT",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS height FLOAT",
    ]
    for sql in migrations:
        try:
            conn.execute(text(sql))
            conn.commit()
        except Exception:
            conn.rollback()

logger.info("Migracoes executadas")

app = FastAPI(title="Sotel Fit Core", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("STARTUP OK")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SHUTDOWN OK")

app.include_router(landbot.router)
app.include_router(clients.router)
app.include_router(auth.router)
app.include_router(admin_router)
app.include_router(cron_router)
app.include_router(twilio_router)
app.include_router(stripe_router)
app.include_router(lead_onboarding_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Sotel Fit Core API"}