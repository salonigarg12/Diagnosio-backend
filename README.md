# EVE Healthcare - Diagnostic Centre Booking & Payment Service

A production-grade backend service built with **FastAPI**, **SQLAlchemy ORM**, **PostgreSQL**, and clean layered architecture (Controller -> Service -> Repository).

---

## 1. End-to-End Happy Flow Diagram

```text
========================================================================================================
                                      DIAGNOSTIC TEST BOOKING HAPPY FLOW
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
       |<-- 200 OK (List of Centres) --| (Cached with In-Memory TTL)  |                         |
       |                               |                              |                         |
  4.   |--- GET /centres/{id} -------->|                              |                         |
       |<-- 200 OK (Tests & Prices) ---|                              |                         |
       |                               |                              |                         |
  5.   |--- POST /bookings/ ---------->|                              |                         |
       |    {                          |--- BookingService ---------->|                         |
       |      "centre_id": 1,          |    .create_multi_test()      |--- CentreRepository --->|
       |      "test_ids": [1, 2],      |                              |    (Verify Test IDs)    |
       |      "appointment_time": ...  |                              |                         |
       |    }                          |                              |--- BookingRepository -->|
       |                               |                              |    (Insert Booking &    |
       |                               |                              |     BookingItems)       |
       |<-- 201 Created (PENDING) -----|                              |<------------------------|
       |                               |                              |                         |
       |  ======================== PAYMENT / WEBHOOK PHASE ===================================  |
       |                               |                              |                         |
  6.   |                               |<-- POST /payments/webhook ---| (Gateway retries / sends)
       |                               |    {                         |                         |
       |                               |      "event_id": "evt_101",  |--- BookingService ----->|
       |                               |      "booking_id": 1,        |    .process_webhook()   |
       |                               |      "status": "SUCCESS"     |                         |
       |                               |    }                         |--- BookingRepository -->|
       |                               |                              |    (Check event_id)     |
       |                               |                              |    [NOT FOUND - FIRST RUN]
       |                               |                              |    - Update -> CONFIRMED|
       |                               |                              |    - Record Payment     |
       |                               |                              |    - Insert WebhookEvent|
       |                               |                              |<------------------------|
       |                               |--- 200 OK (Processed) ------>|                         |
       |                               |                              |                         |
       |  ======================== DIAGNOSTIC LAB LIFECYCLE ==================================  |
       |                               |                              |                         |
  7.   | Phlebotomist collects sample  |--- PATCH /bookings/1/status  |                         |
       |                               |    {"status": "SAMPLE_COLLECTED"}                      |
       |                               |<-- 200 OK -------------------|                         |
       |                               |                              |                         |
  8.   | Lab processes test & generates|--- PATCH /bookings/1/status  |                         |
       | test reports                  |    {"status": "REPORT_GENERATED"}                      |
       |                               |<-- 200 OK -------------------|                         |
       |                               |                              |                         |
  9.   | Report delivered to patient   |--- PATCH /bookings/1/status  |                         |
       |                               |    {"status": "COMPLETED"}   |                         |
       |<-- Booking Flow Completed! ---|<-- 200 OK -------------------|                         |
========================================================================================================
