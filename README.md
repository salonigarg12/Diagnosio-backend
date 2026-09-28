# EVE Healthcare - SDE Intern Backend Service

A backend service built with **FastAPI** and **SQLAlchemy** for diagnostic test bookings, mock payments, and idempotent webhook event processing.

---

## Architecture & System Design

### 1. Database Schema
- **`users`**: Stores user authentication credentials (`id`, `name`, `email`, `password_hash`).
- **`centres`**: Diagnostic centres (`id`, `name`, `location`).
- **`tests`**: Diagnostic test catalogue (`id`, `name`, `description`).
- **`centre_tests`**: Join table mapping tests available at specific centres and their assigned `price`.
- **`bookings`**: Booking lifecycle records (`id`, `user_id`, `centre_id`, `test_id`, `appointment_time`, `amount`, `status`, `created_at`).
  - Supported statuses: `PENDING`, `CONFIRMED`, `FAILED`, `CANCELLED`.
- **`webhook_events`**: Tracks incoming gateway events with a `UNIQUE` constraint on `event_id` to guarantee idempotent execution.

### 2. Webhook Idempotency Strategy
Payment providers guarantee *at-least-once* delivery, leading to duplicate event dispatches during network retries.
- Incoming webhook requests to `POST /payments/webhook/` are checked against `webhook_events.event_id`.
- If the event exists, the API returns `200 OK` immediately without mutating booking state.
- If new, the event is recorded and the booking state transitions accordingly in a single database transaction.

---

## Local Setup & Run

### Prerequisites
- Python 3.10+ installed

### Steps

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd eve-healthcare