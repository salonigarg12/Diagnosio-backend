from fastapi import FastAPI
from app.database import engine, Base, SessionLocal
from app import models
from app.routers import auth, centres, bookings, payments

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare API",
    description="Backend service for diagnostic test bookings and payment processing",
    version="2.0.0"
)

# Seed initial centres and tests if database is empty
def seed_initial_data():
    db = SessionLocal()
    try:
        if db.query(models.Centre).count() == 0:
            c1 = models.Centre(name="Metro Diagnostics", location="Indiranagar, Bangalore")
            c2 = models.Centre(name="Apollo Care Lab", location="Koramangala, Bangalore")
            db.add_all([c1, c2])
            db.flush()

            t1 = models.Test(name="Complete Blood Count (CBC)", description="Full blood profile test")
            t2 = models.Test(name="Lipid Profile", description="Cholesterol and triglyceride assessment")
            t3 = models.Test(name="Thyroid Panel (TSH, T3, T4)", description="Thyroid functioning screening")
            db.add_all([t1, t2, t3])
            db.flush()

            # Map tests to centres with specific pricing
            ct1 = models.CentreTest(centre_id=c1.id, test_id=t1.id, price=350.0)
            ct2 = models.CentreTest(centre_id=c1.id, test_id=t2.id, price=650.0)
            ct3 = models.CentreTest(centre_id=c2.id, test_id=t1.id, price=400.0)
            ct4 = models.CentreTest(centre_id=c2.id, test_id=t3.id, price=500.0)
            db.add_all([ct1, ct2, ct3, ct4])

            db.commit()
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