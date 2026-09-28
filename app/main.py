from fastapi import FastAPI
from app.database import engine, Base, SessionLocal
from app import models
from app.routers import auth, centres, bookings, payments

# 1. Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare Booking Service",
    description="Backend service for diagnostic test bookings, payments, and idempotent webhooks.",
    version="1.0.0"
)

# 2. Seed initial centres and tests if database is fresh
def seed_initial_data():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(models.DiagnosticCentre).count() == 0:
            centre1 = models.DiagnosticCentre(name="Metro Diagnostics", location="Downtown Medical Hub")
            centre2 = models.DiagnosticCentre(name="Apollo Care Lab", location="West Sector Park")
            db.add_all([centre1, centre2])
            db.commit()

            test1 = models.DiagnosticTest(name="Complete Blood Count (CBC)", description="Full blood profile analysis")
            test2 = models.DiagnosticTest(name="Chest X-Ray", description="Digital radiographic image")
            test3 = models.DiagnosticTest(name="Lipid Profile", description="Cholesterol and triglycerides check")
            db.add_all([test1, test2, test3])
            db.commit()

            # Connect tests to centres with specific pricing
            ct1 = models.CentreTest(centre_id=centre1.id, test_id=test1.id, price=350.00)
            ct2 = models.CentreTest(centre_id=centre1.id, test_id=test2.id, price=750.00)
            ct3 = models.CentreTest(centre_id=centre2.id, test_id=test1.id, price=400.00)
            ct4 = models.CentreTest(centre_id=centre2.id, test_id=test3.id, price=900.00)
            db.add_all([ct1, ct2, ct3, ct4])
            db.commit()
    finally:
        db.close()

seed_initial_data()

# 3. Include the endpoint routers
app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)

@app.get("/", tags=["Health Check"])
def root():
    return {"message": "EVE Healthcare API is running"}