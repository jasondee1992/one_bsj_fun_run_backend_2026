# OneBSJ Fun Run Backend 2026

Local MVP backend for the OneBSJ Fun Run Registration System.

## Stack

- FastAPI
- SQLite for local development
- SQLAlchemy ORM
- Pydantic validation
- Mock payment and SMS providers

## Local Setup

```bash
cd /home/udot/PROJECTS/one_bsj_fun_run_backend_2026
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --reload
```

API docs are available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Environment

Default local values are in `.env.example`.

Important values:

- `DATABASE_URL=sqlite:///./data/onebsj_fun_run.db`
- `FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`
- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=admin123`
- `ADMIN_TOKEN_SECRET=change-this-local-secret`
- `BIB_PREFIX=OneBSJ`
- `APP_BASE_URL=http://127.0.0.1:8000`
- `PAYMENT_PROVIDER=mock`
- `PAYMENT_MODE=sandbox`
- `PAYMENT_PUBLIC_KEY=`
- `PAYMENT_SECRET_KEY=`
- `PAYMENT_WEBHOOK_SECRET=`
- `PAYMENT_SESSION_TTL_MINUTES=60`

For local testing, change `ADMIN_TOKEN_SECRET` in `.env`.

## API Response Shape

Most JSON endpoints return:

```json
{
  "success": true,
  "message": "Human readable message",
  "data": {}
}
```

Validation and auth errors use FastAPI's standard error shape.

## Main Endpoints

Public:

- `POST /api/registrations`
- `GET /api/registrations/{registration_id}`
- `GET /api/registrations/{registration_id}/status`

Payments:

- `POST /api/payments/{registration_id}/create`
- `GET /api/payments/{registration_id}`
- `POST /api/payments/{registration_id}/simulate-paid`
- `POST /api/payments/mock-success`
- `POST /api/payments/webhook`

Admin:

- `POST /api/admin/login`
- `GET /api/admin/dashboard/summary`
- `GET /api/admin/registrations`
- `GET /api/admin/registrations/{registration_id}`
- `POST /api/admin/registrations/{registration_id}/resend-sms`
- `GET /api/admin/export/csv`

## Public Registration Payload

```json
{
  "first_name": "Juan",
  "middle_name": "Santos",
  "last_name": "Dela Cruz",
  "suffix": null,
  "address": "123 Main Street",
  "city": "Quezon City",
  "province": "Metro Manila",
  "cellphone_number": "09171234567",
  "email": "juan@example.com",
  "birthday": "1990-01-15",
  "sex": "Male",
  "emergency_contact_name": "Maria Dela Cruz",
  "emergency_contact_number": "09176543210",
  "race_category": "5K",
  "shirt_size": "M",
  "medical_conditions": null,
  "notes": null,
  "waiver_accepted": true,
  "privacy_consent_accepted": true
}
```

Allowed race categories:

- `3K`
- `5K`
- `10K`

Allowed shirt sizes:

- `XS`
- `S`
- `M`
- `L`
- `XL`
- `2XL`
- `3XL`

## Payment Flow

New registrations start as `PENDING_PAYMENT`.

For local testing:

```bash
curl -X POST http://127.0.0.1:8000/api/payments/REG-.../create
```

This returns a sandbox QR payload that the frontend renders as a QR code.

To simulate a successful local payment:

```bash
curl -X POST http://127.0.0.1:8000/api/payments/REG-.../simulate-paid
```

The older mock success endpoint is still available:

```bash
curl -X POST http://127.0.0.1:8000/api/payments/mock-success \
  -H "Content-Type: application/json" \
  -d '{"registration_id":"REG-..."}'
```

Successful payment:

- sets `payment_status` to `PAID`
- assigns the next bib number in successful payment order
- uses the default bib format `OneBSJ-{sequence}`
- writes or updates the payment row
- sends one automatic mock SMS confirmation
- logs the SMS in `sms_logs`

Repeated success calls are idempotent. They return the same paid registration, keep the same bib number, and do not create duplicate automatic SMS logs.

## Webhook Placeholder

`POST /api/payments/webhook` stores incoming webhook payloads in `webhook_events`.

For a success event, send a provider-agnostic payload like:

```json
{
  "source": "mock-provider",
  "event_type": "PAYMENT_SUCCEEDED",
  "external_event_id": "evt_123",
  "data": {
    "registration_id": "REG-...",
    "payment_reference": "PAY-...",
    "provider_transaction_id": "txn_123",
    "amount": 500,
    "currency": "PHP",
    "status": "SUCCEEDED"
  }
}
```

Future PayMongo or Xendit integration should normalize provider-specific webhook payloads into the fields above before calling the payment service.

## Admin Auth

Login:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use the returned token:

```bash
curl http://127.0.0.1:8000/api/admin/dashboard/summary \
  -H "Authorization: Bearer <token>"
```

## CSV Export

```bash
curl http://127.0.0.1:8000/api/admin/export/csv \
  -H "Authorization: Bearer <token>" \
  -o registrations.csv
```

## Smoke Test

After installing dependencies:

```bash
python scripts/smoke_test.py
```

The smoke test creates a registration, marks it paid twice to verify idempotency, logs in as admin, and reads the dashboard summary.

## Frontend Coordination Notes

The nearby frontend folder `/home/udot/PROJECTS/one_bsj_fun_run_fontend_2026` uses:

- `POST /api/registrations` for the registration form
- `POST /api/payments/{registration_id}/create` to create/load the payment QR session
- `GET /api/payments/{registration_id}` for payment refresh polling
- `POST /api/payments/{registration_id}/simulate-paid` for development testing
- `GET /api/registrations/{registration_id}` for final confirmation state
- `POST /api/admin/login` for local admin login
- bearer token auth for admin pages
