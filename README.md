# EVE Healthcare - Diagnostic Centre Booking & Payment Service

A robust, enterprise-grade backend service built with **FastAPI**, **SQLAlchemy ORM**, and **PostgreSQL** (with automated SQLite fallback). The system is architected using a clean **Controller-Service-Repository** pattern to manage diagnostic lab catalogues, multi-test bookings, state machine transitions, and idempotent webhook processing.

---

## 1. System Architecture & Design Pattern

The application strictly decouples business logic, database transactions, and presentation layers:

```text
eve-healthcare-backend/
├── app/
│   ├── constants/          # Domain constants & lifecycle status enums
│   │   ├── __init__.py
│   │   └── enums.py
│   ├── database.py         # Database engine configuration & session dependency
│   ├── models/             # SQLAlchemy ORM relational models
│   │   ├── __init__.py
│   │   └── all_models.py
│   ├── repositories/       # Direct database query & mutation layer
│   │   ├── __init__.py
│   │   ├── booking_repo.py
│   │   └── centre_repo.py
│   ├── services/           # Core business logic, pricing, & orchestration
│   │   ├── __init__.py
│   │   └── booking_service.py
│   ├── routers/            # HTTP endpoints and routing controllers
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── bookings.py
│   │   ├── centres.py
│   │   └── payments.py
│   ├── schemas/            # Pydantic models for request validation & serialization
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── utils/              # Cryptographic security, JWT, and in-memory cache
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   └── security.py
│   └── main.py             # Application entrypoint & table initialization
├── tests/                  # Automated integration and unit test suite
│   ├── __init__.py
│   └── test_api.py
├── .gitignore
├── README.md
└── requirements.txt



========================================================================================================================
                                           END-TO-END BOOKING LIFECYCLE
========================================================================================================================

  [ PATIENT ]                   [ FASTAPI API ]              [ SERVICE / REPO ]                 [ GATEWAY / DB ]
       |                               |                              |                                |
  1.   |--- POST /auth/signup -------->|                              |                                |
       |<-- 201 Created (User Data) ---|                              |                                |
       |                               |                              |                                |
  2.   |--- POST /auth/login --------->|                              |                                |
       |<-- 200 OK (JWT Access Token) -|                              |                                |
       |                               |                              |                                |
  3.   |--- GET /centres ------------->|                              |                                |
       |<-- 200 OK (Centres List) -----| (Served from In-Memory Cache)|                                |
       |                               |                              |                                |
  4.   |--- GET /centres/{id} -------->|                              |                                |
       |<-- 200 OK (Available Tests) -|                              |                                |
       |                               |                              |                                |
  5.   |--- POST /bookings/ ---------->|                              |                                |
       |    {                          |--- BookingService ---------->|                                |
       |      "centre_id": 1,          |    .create_multi_test()      |--- CentreRepository ---------->|
       |      "test_ids": [1, 2],      |                              |    (Verify Test Availability)  |
       |      "appointment_time": ...  |                              |                                |
       |    }                          |                              |--- BookingRepository --------->|
       |                               |                              |    (Save Booking & Line Items) |
       |<-- 201 Created (PENDING) -----|                              |<-------------------------------|
       |                               |                              |                                |
       |  ============================== PAYMENT & WEBHOOK GATEWAY PHASE =============================  |
       |                               |                              |                                |
  6.   |                               |<-- POST /payments/webhook ---| (Gateway Event Dispatch)       |
       |                               |    {                         |                                |
       |                               |      "event_id": "evt_9988", |--- BookingService ------------>|
       |                               |      "booking_id": 1,        |    .process_webhook_event()    |
       |                               |      "status": "SUCCESS"     |                                |
       |                               |    }                         |--- BookingRepository --------->|
       |                               |                              |    (Verify unique event_id)    |
       |                               |                              |    [NOT FOUND - FIRST RUN]     |
       |                               |                              |    - Update -> CONFIRMED       |
       |                               |                              |    - Create Payment Record     |
       |                               |                              |    - Save Webhook Event        |
       |                               |                              |<-------------------------------|
       |                               |--- 200 OK (Processed) ------>|                                |
       |                               |                              |                                |
       |  ============================== DIAGNOSTIC LAB OPERATIONS ===================================  |
       |                               |                              |                                |
  7.   | Technician collects sample    |--- PATCH /bookings/1/status  |                                |
       |                               |    {"status": "SAMPLE_COLLECTED"}                             |
       |                               |<-- 200 OK -------------------|                                |
       |                               |                              |                                |
  8.   | Diagnostic testing complete   |--- PATCH /bookings/1/status  |                                |
       |                               |    {"status": "REPORT_GENERATED"}                             |
       |                               |<-- 200 OK -------------------|                                |
       |                               |                              |                                |
  9.   | Lab uploads final report      |--- PATCH /bookings/1/status  |                                |
       |                               |    {"status": "COMPLETED"}   |                                |
       |<-- Service Lifecycle Complete!|<-- 200 OK -------------------|                                |
========================================================================================================================
