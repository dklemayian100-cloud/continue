# Aluta-style Nightlife Platform (Kenya)

A FastAPI backend for a social nightlife app: users discover venues and DJs,
request songs with tips, reserve tables, and buy event tickets. Venues and DJs
get dashboards, earnings reports, and M-Pesa payouts. Every commission is
recorded in a transaction ledger.

## Features

- **Auth** — phone-number login, bcrypt password hashing, JWT bearer tokens
- **Discovery** — list venues by county
- **Events** — create events, sell tickets with QR codes
- **Ticketing** — 4% platform commission on artist ticket sales
- **Song requests** — tip a DJ to queue a song; 5% platform fee (or flat fee)
- **Table reservations** — 10% platform fee on reservation fee
- **Dashboards** — DJ queue + earnings; venue reservations + earnings
- **Payouts** — DJ/venue request → admin approve → M-Pesa B2C disbursement
- **Ledger** — every tip, ticket, reservation writes an auditable ledger row
- **M-Pesa Daraja** — STK Push (C2B) and B2C payout integration (sandbox-ready)

## Tech stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.x + SQLite (swap to PostgreSQL via `DATABASE_URL`)
- Pydantic v2
- passlib + bcrypt, python-jose (JWT)
- qrcode + Pillow (ticket QR PNG)
- requests + python-dotenv (Daraja API)
- M-Pesa Daraja API (sandbox)

## Getting started (Windows)

```bat
:: 1. clone / create the project folder
D:
mkdir D:\dev\aluta
cd D:\dev\aluta

:: 2. virtualenv
python -m venv venv
venv\Scripts\activate

:: 3. install deps
pip install fastapi uvicorn sqlalchemy "pydantic[email]" python-multipart
pip install "passlib[bcrypt]" "python-jose[cryptography]" qrcode[pil] requests python-dotenv
pip uninstall -y bcrypt
pip install "bcrypt==4.0.1"

:: 4. environment
copy .env.example .env
:: edit .env with your Daraja sandbox credentials

:: 5. run
del aluta.db
uvicorn app.main:app --reload