import logging
import sys
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from core.database import Base, engine
from sqlalchemy import text
from routers import landbot, clients, auth
from routers.admin import router as admin_router
from routers.ai_admin import router as ai_admin_router
from routers.cron import router as cron_router
from routers.twilio_webhook import router as twilio_router
from routers.twilio_status import router as twilio_status_router
from routers.stripe_webhook import router as stripe_router
from routers.lead_onboarding import router as lead_onboarding_router
from routers.stripe_checkout import router as stripe_checkout_router
from routers.observability import router as observability_router
from routers.audit import router as audit_router

from models import *  # noqa
from migrate import run_migrations
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger.info("Importando routers...")

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Banco de dados inicializado")
except Exception as e:
    logger.warning(f"Banco de dados nao disponivel: {e}")

try:
    run_migrations(engine)
except Exception as e:
    logger.error(f"Erro nas migrations: {e}")

app = FastAPI(title="Sotel Fit Core", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000)
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={duration}ms"
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sotel-admin.vercel.app",
        "https://sotel-client.vercel.app",
        "https://frontend-iota-rose-78.vercel.app",
        # Homologacao visual do Treino — origem EXATA de UM deployment de
        # preview, nao um padrao. Previews do cliente nao eram aceitos, o
        # preflight voltava 400 e o navegador bloqueava a chamada; na tela isso
        # aparecia como "E-mail nao encontrado" para uma conta que existia.
        #
        # Por que a origem exata e nao um regex: menor acesso possivel. Um
        # `sotel-client-.*` liberaria todo deployment de preview, presente e
        # futuro, de qualquer branch. Aqui vale UM hostname, que deixa de existir
        # quando a homologacao acabar.
        #
        # REMOVER apos o aceite visual do Proprietario.
        "https://sotel-client-8k6idllvi-sotelfits-projects.vercel.app",
    ],
    # Regra do admin INALTERADA.
    allow_origin_regex=r"https://sotel-admin-git-.*-sotelfits-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Erro nao tratado: {type(exc).__name__}: {exc} | "
        f"path={request.url.path} method={request.method}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor. Tente novamente."}
    )

def scheduled_workout_reminders():
    try:
        from services.workout_reminder import send_workout_reminders
        result = send_workout_reminders()
        logger.info(f"Workout reminders job executado: {result}")
    except Exception as e:
        logger.error(f"Erro em scheduled_workout_reminders: {e}")

def scheduled_checkin_reminders():
    try:
        from services.checkin_reminder import send_checkin_reminders
        result = send_checkin_reminders()
        logger.info(f"Checkin reminders job executado: {result}")
    except Exception as e:
        logger.error(f"Erro em scheduled_checkin_reminders: {e}")

scheduler = BackgroundScheduler()

@app.on_event("startup")
async def startup_event():
    logger.info("STARTUP OK")
    scheduler.add_job(
        scheduled_checkin_reminders,
        CronTrigger(day_of_week="0-4", hour=8, minute=0),
        id="checkin_reminders",
        name="Checkin Reminders",
        replace_existing=True
    )
    scheduler.add_job(
        scheduled_workout_reminders,
        CronTrigger(day_of_week="0-6", hour=7, minute=0),
        id="workout_reminders",
        name="Workout Reminders",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler iniciado")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SHUTDOWN OK")
    if scheduler.running:
        scheduler.shutdown()

app.include_router(landbot.router)
app.include_router(clients.router)
app.include_router(auth.router)
app.include_router(admin_router)
app.include_router(ai_admin_router)
app.include_router(cron_router)
app.include_router(twilio_router)
app.include_router(twilio_status_router)
app.include_router(stripe_router)
app.include_router(lead_onboarding_router)
try:
    from routers.timeline import router as timeline_router
    app.include_router(timeline_router)
    logger.info("Timeline router carregado")
except Exception as e:
    logger.error(f"Timeline router nao carregado: {e}")
try:
    from routers.workout_completion import router as workout_completion_router
    app.include_router(workout_completion_router)
    logger.info("Workout completion router carregado")
except Exception as e:
    logger.error(f"Workout completion router nao carregado: {e}")
try:
    from routers.photos import router as photos_router
    app.include_router(photos_router)
    logger.info("Photos router carregado")
except Exception as e:
    logger.error(f"Photos router nao carregado: {e}")
app.include_router(photos_router)
app.include_router(stripe_checkout_router)
try:
    from routers.body_analysis import router as body_analysis_router
    app.include_router(body_analysis_router)
    logger.info("Body analysis router carregado")
except Exception as e:
    logger.error(f"Body analysis router nao carregado: {e}")
app.include_router(audit_router)
app.include_router(observability_router)
try:
    from routers.exercise import public_router as exercises_router, admin_router as exercises_admin_router
    app.include_router(exercises_router)
    app.include_router(exercises_admin_router)
    logger.info("Exercises router (LIB-003) carregado")
except Exception as e:
    logger.error(f"Exercises router nao carregado: {e}")

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            clients = conn.execute(text("SELECT COUNT(*) FROM clients WHERE status = 'active'")).scalar()
            timeline = conn.execute(text("SELECT COUNT(*) FROM timeline_events")).scalar()
            checkins = conn.execute(text("SELECT COUNT(*) FROM client_checkins")).scalar()
        return {
            "status": "ok",
            "database": "connected",
            "version": "1.0.0",
            "stats": {
                "active_clients": clients,
                "timeline_events": timeline,
                "checkins": checkins,
            }
        }
    except Exception as e:

        logger.error(f"Health check falhou: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "disconnected"}
        )

@app.get("/")
def root():
    return {"message": "Sotel Fit Core API"}



