# Diagnosio (`diagnosio-backend`)

A multi-role diagnostic test booking platform built with **FastAPI**, **SQLAlchemy**, **SQLite / PostgreSQL**, and **Streamlit**. It supports self-service diagnostic centre onboarding, Role-Based Access Control (RBAC), concurrency-safe hourly slot booking (`SELECT ... FOR UPDATE`), multi-test price snapshots, booking cancellation with instant slot release, and idempotent payment webhooks.

- **Repository**: [https://github.com/salonigarg12/diagnosio-backend.git](https://github.com/salonigarg12/diagnosio-backend.git)

---

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend API** | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| **Database & ORM** | SQLAlchemy 2.0, SQLite (zero-config local default), PostgreSQL (`psycopg2-binary` via `DATABASE_URL`) |
| **Auth & Security** | JWT (`python-jose`), direct `bcrypt` password hashing, FastAPI RBAC dependencies |
| **Caching** | Thread-safe in-memory TTL cache (`SimpleCache`) with write-time invalidation |
| **Frontend** | Streamlit + `requests` (strictly decoupled via REST API) |

---

## 1. Problem Statement

Diagnostic booking platforms commonly break down across four operational gaps:

1. **Missing Role Separation & Manual Onboarding**: Without RBAC, diagnostic centres cannot self-onboard or manage their own test catalogues safely without risking unauthorized edits by patients or rival centres.
2. **Slot Overbooking (Race Conditions)**: Checking slot availability and inserting a booking in separate un-locked steps creates a Time-of-Check to Time-of-Use (TOCTOU) race condition when multiple patients book the final spot simultaneously.
3. **Price Drift**: Linking bookings only to live test prices breaks historical accuracy whenever a centre updates its pricing.
4. **Duplicate Payment Processing**: Payment gateways deliver webhooks with at-least-once semantics; processing the same webhook twice can cause duplicate state transitions.

---

## 2. Solution & Approach

Diagnosio solves these issues with a strict **3-tier backend** (`routers` → `services` → `repositories` → `models`) and a decoupled **multi-role Streamlit frontend**:

- **RBAC & Ownership Enforcement**: JWTs embed `user_id` and `role` (`PATIENT` or `CENTRE_ADMIN`). Route dependencies (`require_centre_admin`, `require_patient`) block unauthorized roles with `403 Forbidden`, and service checks enforce `centre.owner_id == current_user.id`.
- **Concurrency-Safe Slot Locking**: Booking creation acquires a pessimistic row lock (`SELECT ... FOR UPDATE` via SQLAlchemy `.with_for_update()`) on the target `Centre` row inside an atomic transaction before checking duplicate user bookings, counting active (`PENDING` / `CONFIRMED`) bookings, and inserting the new booking.
- **Multi-Test Price Snapshots**: Each `Booking` stores one or more `BookingItem` rows capturing `test_name_snapshot` and `price_snapshot` at booking time.
- **Instant Slot Reclamation (PENDING Only)**: Cancelling a `PENDING` booking marks it `CANCELLED` and immediately frees slot capacity for other patients. Once paid and `CONFIRMED`, bookings are locked and cannot be cancelled (`400 Bad Request`).
- **Admin Counter Confirmation & Idempotent Webhooks**: Patients cannot self-approve payments. Centre admins confirm pay-at-centre payments via `POST /payments/bookings/{booking_id}/confirm` (using deterministic event ID `counter-confirm-{booking_id}`), while external payment gateways can call `POST /payments/webhook`. Both paths deduplicate against `webhook_events.event_id`.

### Architecture Diagram

```mermaid
flowchart LR
    subgraph Client["Streamlit Multi-Role Frontend (Port 8501)"]
        ST["frontend/streamlit_app.py<br/>Patient Tabs · Centre Admin Tabs<br/>st.session_state (JWT + Role)"]
    end

    subgraph Backend["FastAPI 3-Tier Backend (Port 8000)"]
        R["Routers<br/>auth · centres · bookings · payments<br/>(HTTP + RBAC Guards)"]
        S["Services<br/>Business Rules · Atomic Transactions<br/>Ownership Checks · Cache Invalidation"]
        C["SimpleCache<br/>In-Memory TTL Cache"]
        REPO["Repositories<br/>SQLAlchemy Queries<br/>SELECT ... FOR UPDATE"]
    end

    subgraph DB["Persistence"]
        SQL[("SQLite (Local Default)<br/>or PostgreSQL (Production)")]
    end

    ST -- "REST JSON + Bearer JWT" --> R
    R --> S
    S <--> C
    S --> REPO
    REPO --> SQL
```

### Database / ER Diagram

```mermaid
erDiagram
    USERS ||--o| CENTRES : "owns (CENTRE_ADMIN)"
    USERS ||--o{ BOOKINGS : "places (PATIENT)"
    CENTRES ||--o{ CENTRE_TESTS : "offers"
    TESTS ||--o{ CENTRE_TESTS : "catalogued_in"
    CENTRES ||--o{ BOOKINGS : "hosts"
    BOOKINGS ||--|{ BOOKING_ITEMS : "contains"
    CENTRE_TESTS ||--o{ BOOKING_ITEMS : "snapshotted_by"
    BOOKINGS ||--|| PAYMENTS : "paid_via"
    BOOKINGS ||--o{ WEBHOOK_EVENTS : "audited_by"

    USERS {
        int id PK
        string full_name
        string email UK
        string hashed_password
        enum role "PATIENT | CENTRE_ADMIN"
        datetime created_at
    }

    CENTRES {
        int id PK
        int owner_id FK,UK
        string name
        string city
        string address
        int opening_hour
        int closing_hour
        int max_capacity_per_slot
        datetime created_at
    }

    TESTS {
        int id PK
        string name UK
        text description
        datetime created_at
    }

    CENTRE_TESTS {
        int id PK
        int centre_id FK
        int test_id FK
        numeric price
        boolean is_available
    }

    BOOKINGS {
        int id PK
        int user_id FK
        int centre_id FK
        datetime appointment_time
        numeric total_amount
        enum status "PENDING | CONFIRMED | CANCELLED"
        datetime created_at
        datetime updated_at
    }

    BOOKING_ITEMS {
        int id PK
        int booking_id FK
        int centre_test_id FK
        string test_name_snapshot
        numeric price_snapshot
    }

    PAYMENTS {
        int id PK
        int booking_id FK,UK
        numeric amount
        enum status "PENDING | SUCCESS | FAILED"
        string transaction_ref UK
        datetime created_at
        datetime updated_at
    }

    WEBHOOK_EVENTS {
        int id PK
        string event_id UK
        string event_type
        int booking_id FK
        text payload
        datetime processed_at
    }
```

### API Workflow / Sequence Diagram

```mermaid
sequenceDiagram
    actor PatientA as Patient A
    actor PatientB as Patient B
    actor Admin as Centre Admin
    participant API as FastAPI (Router + Service)
    participant DB as SQLAlchemy / Database

    Note over PatientA,DB: Concurrency-Safe Booking (Slot Capacity = 1)
    par Simultaneous Requests for 10:00 Slot
        PatientA->>API: POST /bookings/ (Bearer JWT)
        PatientB->>API: POST /bookings/ (Bearer JWT)
    end

    API->>DB: BEGIN and SELECT * FROM centres WHERE id = 1 FOR UPDATE (Tx A acquires lock)
    API->>DB: BEGIN and SELECT * FROM centres WHERE id = 1 FOR UPDATE (Tx B waits)
    API->>DB: Check duplicate & count active bookings (count = 0 < 1)
    API->>DB: INSERT booking (PENDING), booking_items, payment and COMMIT
    API-->>PatientA: 201 Created (Booking #1, PENDING)

    Note over API,DB: Lock released — Tx B resumes
    API->>DB: Count active bookings (count = 1 >= 1)
    API->>DB: ROLLBACK
    API-->>PatientB: 409 Conflict ("Selected time slot is fully booked.")

    Note over Admin,DB: Centre Admin Payment Confirmation and Idempotent Webhook Replay
    Admin->>API: POST /payments/bookings/1/confirm (Bearer Admin JWT)
    API->>DB: Verify centre ownership and PENDING status
    API->>DB: Check webhook_events (counter-confirm-1) then set Payment=SUCCESS, Booking=CONFIRMED
    API-->>Admin: 200 OK (idempotent_replay=false)

    Admin->>API: Replay POST /payments/webhook (event_id=counter-confirm-1)
    API->>DB: Check webhook_events (already processed)
    API-->>Admin: 200 OK (idempotent_replay=true)
```

---

## 3. Project Structure

```text
diagnosio-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entrypoint, CORS, startup table creation
│   ├── auth.py                     # JWT extraction & RBAC guards (require_centre_admin, require_patient)
│   ├── database.py                 # SQLAlchemy engine (SQLite default / PostgreSQL via DATABASE_URL)
│   ├── schemas.py                  # Pydantic v2 request/response models & validators
│   ├── constants/
│   │   ├── __init__.py
│   │   └── enums.py                # UserRole, BookingStatus, PaymentStatus
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                 # User model
│   │   ├── centre.py               # Centre, Test, CentreTest models
│   │   ├── booking.py              # Booking, BookingItem models
│   │   └── payment.py              # Payment, WebhookEvent models
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repo.py            # User queries
│   │   ├── centre_repo.py          # Centre, Test, CentreTest queries
│   │   ├── booking_repo.py         # FOR UPDATE locking, slot counts, booking queries
│   │   └── payment_repo.py         # Payment & WebhookEvent queries
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py         # Registration & login with JWT issuance
│   │   ├── centre_service.py       # Onboarding, test management, TTL cache, hourly slots
│   │   ├── booking_service.py      # Atomic slot booking, snapshots, cancellation
│   │   └── payment_service.py      # Idempotent payment webhook handling
│   └── utils/
│       ├── __init__.py
│       ├── cache.py                # Thread-safe TTL SimpleCache
│       ├── logger.py               # Structured stdout logger
│       └── security.py             # Direct bcrypt hashing & JWT creation/decoding
├── frontend/
│   └── streamlit_app.py            # Multi-role Streamlit UI (REST API only)
├── .gitignore                      # Python & local DB ignore rules
├── requirements.txt                # Python dependencies
└── README.md
```

---

## 4. API Documentation

Interactive Swagger documentation is served automatically at `http://127.0.0.1:8000/docs`.

| Method | Endpoint | Access / RBAC | Description | Key Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Service health check | `200` |
| `POST` | `/auth/register` | Public | Register `PATIENT` or `CENTRE_ADMIN` and return JWT | `201`, `409` |
| `POST` | `/auth/login` | Public | Authenticate user and return JWT with `user_id` and `role` | `200`, `401` |
| `GET` | `/auth/me` | Authenticated | Return current authenticated user profile | `200`, `401` |
| `GET` | `/centres/` | Public | Search/filter onboarded centres & available tests (TTL cached) | `200` |
| `GET` | `/centres/{centre_id}/slots` | Public | Get fixed 1-hour slots & remaining capacity for a date (`?booking_date=YYYY-MM-DD`) | `200`, `404` |
| `POST` | `/centres/` | `CENTRE_ADMIN` | Onboard a diagnostic centre (enforces 1 centre per admin) | `201`, `400`, `403` |
| `POST` | `/centres/{centre_id}/tests` | `CENTRE_ADMIN` (Owner) | Add/update diagnostic test & price; invalidates catalogue cache | `201`, `403`, `404` |
| `GET` | `/centres/my-centre` | `CENTRE_ADMIN` | Get admin's centre profile, tests, stats, & filtered bookings (`?booking_date=&status=`) | `200`, `403`, `404` |
| `POST` | `/bookings/` | `PATIENT` | Concurrency-safe multi-test slot booking with price snapshots | `201`, `400`, `403`, `409` |
| `GET` | `/bookings/my` | `PATIENT` | List personal bookings with line-item snapshots & payment status | `200`, `403` |
| `POST` | `/bookings/{booking_id}/cancel` | `PATIENT` (Owner) | Cancel a `PENDING` booking and release slot capacity (`CONFIRMED` bookings return `400`) | `200`, `400`, `403`, `404` |
| `POST` | `/payments/bookings/{booking_id}/confirm` | `CENTRE_ADMIN` (Owner) | Confirm pay-at-centre payment for a `PENDING` booking via idempotent `counter-confirm-{id}` event | `200`, `400`, `403`, `404`, `409` |
| `POST` | `/payments/webhook` | External Gateway | Idempotently confirm/fail payment callback via unique `event_id` | `200`, `404`, `409` |

---

## 5. Design Decisions & Assumptions

### Key Design Decisions

- **Zero-Friction Local DB with Production PostgreSQL Readiness**: `app/database.py` defaults to `sqlite:///./diagnosio.db` with automatic table creation on startup (`Base.metadata.create_all`) so anyone can clone and run the project immediately. Setting `DATABASE_URL` seamlessly switches to PostgreSQL where `.with_for_update()` executes native row-level locking (`SELECT ... FOR UPDATE`).
- **Pessimistic Row Locking on Centre (.with_for_update())**: Instead of pre-generating thousands of empty slot rows or relying on retry-heavy optimistic locking, locking the parent `Centre` row serializes competing bookings for that facility inside an atomic transaction.
- **Direct bcrypt**: `app/utils/security.py` uses `bcrypt` directly rather than `passlib`, avoiding `passlib` compatibility breaks on Python 3.11+ with modern `bcrypt` releases.
- **Strict 3-Tier Layering**: Routers only validate input and enforce auth dependencies; Services own transactions, business rules, and cache invalidation; Repositories contain all SQLAlchemy queries.
- **Normalized Catalogue + Price Snapshots (Test -> CentreTest -> BookingItem)**: Separating master tests from per-centre pricing allows multiple centres to price the same test independently, while `BookingItem` snapshots guarantee historical receipts never mutate when prices change.
- **TTL Cache with Write-Time Invalidation**: Public `GET /centres/` queries are cached in `SimpleCache` (5-minute TTL) and immediately cleared whenever a centre is onboarded or its tests/prices are modified.
- **Pure REST Decoupling in Streamlit**: `frontend/streamlit_app.py` communicates solely via HTTP (`requests`) and stores session tokens in `st.session_state`, keeping the UI completely independent of backend models and database sessions.

### Assumptions

- **Fixed 1-Hour Slots**: Bookable slots are generated dynamically in 1-hour increments between `opening_hour` and `closing_hour` (e.g., `09:00–17:00` produces 8 hourly slots). `appointment_time` must align to the top of the hour (`MM:SS = 00:00`).
- **One Centre per Admin**: Each `CENTRE_ADMIN` account owns at most one diagnostic centre (`centres.owner_id` has a unique constraint).
- **Pay-at-Centre Admin Confirmation & External Gateway Webhook**: Diagnosio is a diagnostic booking platform rather than a payment processor, so patients cannot self-confirm payments. Payment confirmation is performed by the owning `CENTRE_ADMIN` at check-in (`POST /payments/bookings/{booking_id}/confirm`, triggering idempotent event `counter-confirm-{booking_id}`) or by an external payment gateway calling `POST /payments/webhook`.
- **PENDING-Only Cancellation**: Patients can cancel unpaid `PENDING` bookings to immediately release the slot for other patients. Once confirmed and paid (`CONFIRMED`), bookings are locked against cancellation (`400 Bad Request`).
- **Single-Timezone Local Scheduling**: `appointment_time` is stored as a naive local clinic datetime so date and hour comparisons align directly with `opening_hour` / `closing_hour`.

---

## 6. Local Setup

### Prerequisites
- Python 3.11+

### Step 1: Clone & Install Dependencies
```bash
git clone https://github.com/salonigarg12/diagnosio-backend.git
cd diagnosio-backend

python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Database Configuration (SQLite Default or PostgreSQL)
- **Default (SQLite — no setup required):** Tables are created automatically in `./diagnosio.db` when FastAPI starts.
- **Optional (PostgreSQL):** Set `DATABASE_URL` before starting the server:
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/diagnosio"
export JWT_SECRET_KEY="change-this-to-a-strong-random-secret"
```

### Step 3: Start the FastAPI Backend (Terminal 1)
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Verify at `http://127.0.0.1:8000/health` and inspect interactive OpenAPI docs at `http://127.0.0.1:8000/docs`.

### Step 4: Start the Streamlit Frontend (Terminal 2)
```bash
streamlit run frontend/streamlit_app.py
```
Open `http://localhost:8501` in your browser.

---

## 7. End-to-End Verification Walkthrough

Verify every core workflow directly through the **Streamlit UI** (`http://localhost:8501`) and **Swagger UI** (`http://127.0.0.1:8000/docs`):

1. **Centre Onboarding & Test Management (CENTRE_ADMIN)**
   - Register an account with role **Diagnostic Centre Admin**.
   - In **Centre Onboarding & Profile**, register a centre with `max_capacity_per_slot = 1` (e.g., `09:00` to `17:00`).
   - In **Manage Diagnostic Tests**, add two tests (e.g., `Complete Blood Count` at `Rs. 500`, `Lipid Profile` at `Rs. 900`).
2. **RBAC Guard Verification (403 Forbidden)**
   - Register a **Patient** account and attempt to call `POST /centres/` via Swagger UI using the Patient's Bearer token → verify the API returns **403 Forbidden**.
3. **Multi-Test Booking & Slot Capacity Check (201 vs 409)**
   - As **Patient 1**, browse the centre, select both tests, pick an hourly slot (e.g., `10:00 - 11:00`), and click **Confirm Slot Booking** → verify **201 Created** (`total_amount = 1400.00`).
   - Register **Patient 2** in a separate browser/incognito tab and attempt to book the exact same `10:00 - 11:00` slot → verify **409 Conflict** ("Selected time slot is fully booked.").
   - Attempt to re-book the same slot as **Patient 1** → verify duplicate-booking protection returns **409 Conflict**.
4. **PENDING Cancellation & Instant Slot Release**
   - In **My Bookings**, verify **Patient 1** sees **"Awaiting payment confirmation at diagnostic centre"** alongside **Cancel Booking** (with no self-payment button).
   - Click **Cancel Booking** on the `PENDING` booking → status becomes `CANCELLED`.
   - Refresh slots as **Patient 2** → the `10:00 - 11:00` slot immediately shows `1/1 spots left` and can now be booked by **Patient 2**.
5. **Centre Admin Payment Confirmation & Idempotent Webhook Replay**
   - Log in as the **Diagnostic Centre Admin** and open **Centre Appointments Dashboard** → filter by date and status to inspect incoming patient bookings.
   - For **Patient 2**'s `PENDING` booking, click **Confirm Payment (Paid at Centre)** (`POST /payments/bookings/{booking_id}/confirm`) → booking transitions to `CONFIRMED` and payment becomes `SUCCESS`.
   - Replay `POST /payments/webhook` in Swagger UI with `event_id = "counter-confirm-{booking_id}"` → verify **200 OK** with `"idempotent_replay": true`.
6. **Confirmed Booking Lock Verification (400 Bad Request)**
   - Log back in as **Patient 2** and open **My Bookings** → verify the booking displays **"Confirmed & Paid (Locked)"** with no Cancel button.
   - Attempt to call `POST /bookings/{booking_id}/cancel` via Swagger UI using **Patient 2**'s Bearer token → verify the API rejects it with **400 Bad Request** (`"Confirmed bookings cannot be cancelled."`).

---

## 8. Limitations & Future Improvements

- **Database Migrations**: Currently initializes tables via `Base.metadata.create_all()`. Production deployments should adopt **Alembic** for versioned schema migrations.
- **SQLite vs. PostgreSQL Locking**: SQLite handles local development with database-level write locking, whereas production multi-worker concurrency requires PostgreSQL (`DATABASE_URL`) for true row-level `SELECT ... FOR UPDATE` locking.
- **Distributed Caching**: `SimpleCache` is process-local. Multi-worker deployments should swap it for **Redis** so cache invalidations propagate across workers.
- **Webhook Signature Verification**: Add HMAC signature verification (e.g., Razorpay/Stripe webhook secrets) on `POST /payments/webhook` before accepting payment callbacks in production.
- **Granular Locking**: Locking the `Centre` row serializes all slots for a centre; at very high scale, locking a dedicated `(centre_id, slot_time)` slot record would increase throughput across distinct hours.
- **Timezone & Refund Handling**: Store timezone-aware timestamps per centre city, and add refund workflows if future business rules allow post-confirmation cancellations.

---

## 9. Requirements Checklist

- [x] **RBAC & Roles**: `UserRole` (`PATIENT`, `CENTRE_ADMIN`) added to `User`, embedded in JWT claims and login/register responses, enforced via `require_centre_admin` and `require_patient` (`403 Forbidden`).
- [x] **Self-Service Centre Onboarding**: `POST /centres/` (1 centre per admin), `POST /centres/{centre_id}/tests` (owner-verified + `SimpleCache` invalidation), and `GET /centres/my-centre` dashboard endpoint.
- [x] **Preserved Data Model**: Retained `Centre`, `Test`, `CentreTest`, `Booking`, `BookingItem` (multi-test snapshots), `Payment`, and `WebhookEvent`.
- [x] **Concurrency-Safe Slot Booking**: Atomic transaction using SQLAlchemy `.with_for_update()` on `Centre`, active (`PENDING`/`CONFIRMED`) capacity count, duplicate-booking check, and `409 Conflict` handling.
- [x] **Fixed 1-Hour Slots & PENDING-Only Cancellation**: Dynamic 1-hour slot generation from operating hours, instant slot reclamation when `PENDING` bookings are cancelled, and `400 Bad Request` lock preventing cancellation of `CONFIRMED` bookings.
- [x] **Centre Admin Payment Confirmation & Idempotent Webhooks**: Owning `CENTRE_ADMIN` confirms pay-at-centre bookings via `POST /payments/bookings/{booking_id}/confirm` (`counter-confirm-{booking_id}`), alongside external gateway support at `POST /payments/webhook` deduplicated via `WebhookEvent.event_id`.
- [x] **Strict 3-Tier Architecture**: Zero direct database/repository calls inside FastAPI routers.
- [x] **Pure Native Streamlit Frontend**: Multi-role Patient and Centre Admin views in `frontend/streamlit_app.py` using standard Streamlit widgets and REST API calls only.
- [x] **Direct bcrypt**: Password hashing uses `bcrypt` directly for full Python 3.11+ compatibility.
