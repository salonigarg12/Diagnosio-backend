# EVE Healthcare — Diagnostic Centre Booking & Payment Service

A production-grade backend service built with **FastAPI**, **SQLAlchemy ORM**, and **PostgreSQL** (with automated SQLite fallback). The platform is architected using the **Controller-Service-Repository** pattern to manage diagnostic lab catalogues, multi-test bookings, state machine transitions, and idempotent webhook processing.

---

## 1. Problem Statement

Diagnostic centre aggregators and lab service platforms encounter critical operational challenges:
1. **Catalog & Pricing Variability:** Diagnostic centres offer overlapping yet distinct subsets of tests at location-dependent rates.
2. **Cart & Multi-Item Bookings:** Patients routinely schedule multiple tests within a single appointment slot, requiring transactional line-item integrity.
3. **State Machine Integrity:** The booking lifecycle must follow strict medical workflow transitions (`PENDING` -> `CONFIRMED` -> `SAMPLE_COLLECTED` -> `REPORT_GENERATED` -> `COMPLETED`) to prevent unauthorized cancellations or invalid status updates.
4. **Payment Gateway Retries:** Payment providers dispatch webhooks using *at-least-once* delivery. Network retries can trigger duplicate processing, risking double confirmations or duplicate ledger writes.

---

## 2. Solution & High-Level Architecture

The service resolves these requirements through a decoupled 3-tier enterprise architecture:

```text
+-----------------------------------------------------------------------------------+
|                                 PRESENTATION LAYER                                |
|             FastAPI Routers (/auth, /centres, /bookings, /payments)               |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                               BUSINESS SERVICE LAYER                              |
|           BookingService (Pricing Engine, Multi-test Cart Validation)             |
|           PaymentService (Webhook Idempotency Guard, Ledger Records)              |
+---------------------+-------------------------------------+-----------------------+
                      |                                     |
                      v                                     v
+---------------------------------------+ +-----------------------------------------+
|           DATA ACCESS LAYER           | |               UTILS LAYER               |
| CentreRepository & BookingRepository  | |  Security (Bcrypt/JWT), Cache (TTL)     |
+---------------------+-----------------+ +-----------------------------------------+
                      |
                      v
+-----------------------------------------------------------------------------------+
|                                PERSISTENCE LAYER                                  |
|               PostgreSQL / SQLite Database Engine (6 Relational Tables)           |
+-----------------------------------------------------------------------------------+
```

---

## 3. Database Architecture (ER Diagram)

```text
  +------------------+             +-----------------------+             +------------------+
  |      users       |             |        centres        |             |      tests       |
  +------------------+             +-----------------------+             +------------------+
  | id (PK)          |             | id (PK)               |             | id (PK)          |
  | name             |             | name                  |             | name             |
  | email (UQ)       |             | location              |             | description      |
  | password_hash    |             +-----------+-----------+             +--------+---------+
  | created_at       |                         |                                  |
  +--------+---------+                         | 1                                | 1
           | 1                                 |                                  |
           |                                   |          +-----------------------+
           |                                   |          |
           |                                   | N        | N
           |                           +-------+----------+--------+
           |                           |       centre_tests        |
           |                           +---------------------------+
           |                           | id (PK)                   |
           |                           | centre_id (FK -> centres) |
           |                           | test_id   (FK -> tests)   |
           |                           | price                     |
           |                           +---------------------------+
           |
           | N
  +--------+------------------+        +---------------------------+
  |         bookings          | 1    N |       booking_items       |
  +---------------------------+--------+---------------------------+
  | id (PK)                   |        | id (PK)                   |
  | user_id (FK -> users)     |        | booking_id (FK -> bookings|
  | centre_id (FK -> centres) |        | test_id (FK -> tests)     |
  | appointment_time          |        | price_at_booking          |
  | total_amount              |        +---------------------------+
  | status (Enum)             |
  | created_at                |        +---------------------------+
  +--------+------------------+        |      webhook_events       |
           | 1                         +---------------------------+
           |                           | id (PK)                   |
           | N                         | event_id (UQ, Indexed)    |
  +--------+------------------+        | booking_id                |
  |         payments          |        | status                    |
  +---------------------------+        | processed_at              |
  | id (PK)                   |        +---------------------------+
  | booking_id (FK->bookings) |
  | amount                    |
  | status (Enum)             |
  | transaction_id            |
  | created_at                |
  +---------------------------+
```

---

## 4. End-to-End Patient & Lab Workflow

```text
========================================================================================================
                                     END-TO-END PATIENT & LAB WORKFLOW
========================================================================================================

  [ PATIENT ]                   [ FASTAPI API ]              [ SERVICE / REPO ]         [ GATEWAY / DB ]
       |                               |                              |                         |
  1.   |--- POST /auth/signup -------->|                              |                         |
       |<-- 201 Created (User Data) ---|                              |                         |
       |                               |                              |                         |
  2.   |--- POST /auth/login --------->|                              |                         |
       |<-- 200 OK (JWT Access Token) -|                              |                         |
       |                               |                              |                         |
  3.   |--- GET /centres ------------->|                              |                         |
       |<-- 200 OK (Centres List) -----| (Served via In-Memory Cache) |                         |
       |                               |                              |                         |
  4.   |--- GET /centres/{id} -------->|                              |                         |
       |<-- 200 OK (Tests & Prices) ---|                              |                         |
       |                               |                              |                         |
  5.   |--- POST /bookings/ ---------->|                              |                         |
       |    {                          |--- BookingService ---------->|                         |
       |      "centre_id": 1,          |    .create_multi_test()      |--- CentreRepository --->|
       |      "test_ids": [1, 2],      |                              |    (Validate test IDs)  |
       |      "appointment_time": ...  |                              |                         |
       |    }                          |                              |--- BookingRepository -->|
       |                               |                              |    (Save Booking & Items|
       |<-- 201 Created (PENDING) -----|                              |<------------------------|
       |                               |                              |                         |
       |  ============================== PAYMENT / WEBHOOK PHASE =============================  |
       |                               |                              |                         |
  6.   |                               |<-- POST /payments/webhook ---| (Gateway retry/event)   |
       |                               |    {                         |                         |
       |                               |      "event_id": "evt_9988", |--- PaymentService ----->|
       |                               |      "booking_id": 1,        |    .process_webhook()   |
       |                               |      "status": "SUCCESS"     |                         |
       |                               |    }                         |--- BookingRepository -->|
       |                               |                              |    (Check event_id)     |
       |                               |                              |    [NEW EVENT]          |
       |                               |                              |    - State -> CONFIRMED |
       |                               |                              |    - Log in payments    |
       |                               |                              |    - Record in events   |
       |                               |                              |<------------------------|
       |                               |--- 200 OK (Processed) ------>|                         |
       |                               |                              |                         |
       |  ============================== DIAGNOSTIC LAB OPERATIONS ===========================  |
       |                               |                              |                         |
  7.   | Phlebotomist collects sample  |--- PATCH /bookings/1/status  |                         |
       |                               |    {"status": "SAMPLE_COLLECTED"}                      |
       |                               |<-- 200 OK -------------------|                         |
       |                               |                              |                         |
  8.   | Lab processes test specimens  |--- PATCH /bookings/1/status  |                         |
       |                               |    {"status": "REPORT_GENERATED"}                      |
       |                               |<-- 200 OK -------------------|                         |
       |                               |                              |                         |
  9.   | Lab uploads final report      |--- PATCH /bookings/1/status  |                         |
       |                               |    {"status": "COMPLETED"}   |                         |
       |<-- Complete Service Journey --|<-- 200 OK -------------------|                         |
========================================================================================================
```

---

## 5. Project Structure

```text
eve-healthcare-backend/
├── app/
│   ├── constants/
│   │   ├── __init__.py
│   │   └── enums.py          # BookingStatus and PaymentStatus domain enums
│   ├── database.py           # Engine setup, session factories, and base classes
│   ├── models/
│   │   ├── __init__.py
│   │   ├── booking.py        # Booking and BookingItem schemas
│   │   ├── centre.py         # Centre, Test, and CentreTest schemas
│   │   ├── payment.py        # Payment ledger and WebhookEvent schemas
│   │   └── user.py           # User entity schema
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── booking_repo.py   # Bookings, payments, and webhook data queries
│   │   └── centre_repo.py    # Diagnostic centres and test catalogue data queries
│   ├── services/
│   │   ├── __init__.py
│   │   ├── booking_service.py# Cart validation and pricing aggregation
│   │   └── payment_service.py# Webhook idempotency guard & ledger updates
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py           # User registration and login
│   │   ├── bookings.py       # Cart booking and status tracking
│   │   ├── centres.py        # Diagnostic centre discovery and catalogues
│   │   └── payments.py       # Webhook ingestion and simulation
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic v2 validation models
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cache.py          # In-memory TTL catalogue caching
│   │   └── security.py       # Bcrypt password hashing and JWT token handling
│   └── main.py               # FastAPI entrypoint and initial catalogue seed
├── tests/
│   ├── __init__.py
│   └── test_api.py           # Automated integration test suite
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 6. Tech Stack

* **Language:** Python 3.10+
* **Framework:** FastAPI
* **ORM:** SQLAlchemy (declarative models, session transactions)
* **Database:** PostgreSQL (with automated fallback to SQLite for local development)
* **Security & Auth:** Direct Bcrypt, Python-Jose (JWT tokens)
* **Validation:** Pydantic v2
* **Testing:** Pytest, HTTPX

------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------------------------------------


## 7. Environment Setup & Running the Application

### Prerequisites

Make sure the following are installed:

* Python 3.10+
* `pip`
* PostgreSQL (optional — SQLite is used as a fallback for local development)
* Git

### 1. Clone the Repository

```bash
git clone https://github.com/salonigarg12/eve-healthcare-backend.git
cd eve-healthcare-backend
```

### 2. Create and Activate a Virtual Environment

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

The application is designed to use PostgreSQL in a production environment and automatically falls back to SQLite for local development when PostgreSQL is not configured.

If using PostgreSQL, make sure the PostgreSQL server is running and configure the database connection according to the application's database configuration.

For local development, no separate database server is required when the SQLite fallback is used.

### 5. Run the Application

Start the FastAPI development server with:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### 6. API Documentation

FastAPI automatically provides interactive API documentation.

**Swagger UI:**

```text
http://127.0.0.1:8000/docs
```

**ReDoc:**

```text
http://127.0.0.1:8000/redoc
```

### 7. Run Tests

Run the complete automated test suite using:

```bash
pytest
```

For more detailed test output:

```bash
pytest -v
```

### Quick Start

For a local development setup using the SQLite fallback:

```bash
git clone https://github.com/salonigarg12/eve-healthcare-backend.git
cd eve-healthcare-backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` to explore the API.
