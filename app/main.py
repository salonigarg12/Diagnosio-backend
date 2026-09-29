import time
import uuid
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import engine, Base, SessionLocal
from app import models
from app.routers import auth, centres, bookings, payments
from app.utils.logger import logger, request_id_ctx

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare API",
    description="Backend service for diagnostic test bookings and payment processing",
    version="2.0.0"
)

class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        logger.info(f"Incoming request: {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Completed {request.method} {request.url.path} "
                f"with status {response.status_code} in {duration_ms:.2f}ms"
            )
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unhandled exception on {request.method} {request.url.path} after {duration_ms:.2f}ms: {exc}",
                exc_info=True
            )
            raise exc
        finally:
            request_id_ctx.reset(token)

app.add_middleware(RequestCorrelationMiddleware)

# Seed initial centres and tests if database is empty
def seed_initial_data():
    db = SessionLocal()
    try:
        if db.query(models.Centre).count() == 0:
            logger.info("Initializing baseline catalogue seed data...")
            c1 = models.Centre(name="Metro Diagnostics", location="Indiranagar, Bangalore")
            c2 = models.ApolloCareLab = models.Centre(name="Apollo Care Lab", location="Koramangala, Bangalore")
            db.add_all([c1, c2])
            db.flush()

            t1 = models.Test(name="Complete Blood Count (CBC)", description="Full blood profile test")
            t2 = models.Test(name="Lipid Profile", description="Cholesterol and triglyceride assessment")
            t3 = models.Test(name="Thyroid Panel (TSH, T3, T4)", description="Thyroid functioning screening")
            db.add_all([t1, t2, t3])
            db.flush()

            ct1 = models.CentreTest(centre_id=c1.id, test_id=t1.id, price=350.0)
            ct2 = models.CentreTest(centre_id=c1.id, test_id=t2.id, price=650.0)
            ct3 = models.CentreTest(centre_id=c2.id, test_id=t1.id, price=400.0)
            ct4 = models.CentreTest(centre_id=c2.id, test_id=t3.id, price=500.0)
            db.add_all([ct1, ct2, ct3, ct4])

            db.commit()
            logger.info("Baseline catalogue seed completed successfully.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Error seeding database: {exc}", exc_info=True)
    finally:
        db.close()

seed_initial_data()

# Register Routers
app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)

@app.get("/", tags=["Health Check"])
def root():
    return {"message": "EVE Healthcare API is running"}