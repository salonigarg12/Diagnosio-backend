from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import (  # noqa: F401 - ensure all ORM models are registered before create_all
    Booking,
    BookingItem,
    Centre,
    CentreTest,
    Payment,
    Test,
    User,
    WebhookEvent,
)
from app.routers import auth, bookings, centres, payments
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Diagnosio API (diagnosio-backend)",
    description=(
        "Multi-role diagnostic centre booking backend with RBAC, self-service centre "
        "onboarding, PostgreSQL row-level slot locking, and idempotent payment webhooks."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "diagnosio"}
