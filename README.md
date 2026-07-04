# PSX Portfolio Tracker

A full-stack application for tracking stock portfolios on the **Pakistan Stock Exchange (PSX)**. The application features a Python/Flask REST API backend powered by SQLAlchemy and PostgreSQL (Supabase), and a modern React frontend built with Vite and Tailwind CSS.

---

## Architecture Overview

```
                     ┌──────────────────┐
                     │  React Frontend  │
                     │  (Vite + React)  │
                     └────────┬─────────┘
                              │ REST API
                              ▼
                     ┌──────────────────┐
                     │  Flask Backend   │
                     │   (Python App)   │
                     └────────┬─────────┘
                              │ SQLAlchemy ORM
                              ▼
                     ┌──────────────────┐
                     │ Supabase DB (PG) │
                     └──────────────────┘
```

- **Backend**: Flask 3.x with SQLAlchemy 2.x ORM, structured with the Application Factory pattern. Utilizes database migrations via Flask-Migrate (Alembic) and fetches daily market data through `psxdata`.
- **Frontend**: Single Page Application built with React, Vite, and tailwind styling. Authenticates and interacts directly with Supabase client-side for real-time capabilities where appropriate, and communicates with the Flask server for analytical and portfolio calculations.
- **Database**: Supabase PostgreSQL hosting schema with database-level constraints for transactional integrity.

---

## Directory Structure

```
PSX/ (Root)
├── backend/              # Flask Backend workspace
│   ├── app/              # Backend Python application package
│   │   ├── api/          # API blueprints & routes (/api/v1)
│   │   ├── models/       # SQLAlchemy database models
│   │   ├── services/     # Business logic & background services
│   │   ├── config.py     # Configuration management
│   │   ├── extensions.py # Shared DB & Migrate extensions
│   │   └── __init__.py   # Application factory
│   ├── migrations/       # Alembic database migration scripts
│   ├── scripts/          # Ingestion / seeding CLI scripts
│   ├── tests/            # Test suite for backend logic
│   ├── .env.example      # Template for backend settings
│   ├── requirements.txt  # Python package list
│   └── run.py            # Flask entry point script
├── docs/                 # Design specs and project documentation
│   └── trading-journal-spec.md
├── frontend/             # React/Vite Frontend application
│   ├── src/              # React components, pages, hooks and styles
│   ├── public/           # Static public assets
│   ├── package.json      # Node dependency manifest
│   ├── vite.config.js    # Vite configuration
│   └── .env.example      # Template for frontend environment variables
├── .gitignore            # Root-level gitignore
└── README.md             # Root-level README
```

---

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher (with npm)
- A Supabase account and database project

---

### 1. Backend Setup

1. **Navigate to the backend directory and create a virtual environment:**
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install Python dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in your Supabase connection strings and secrets:
   ```powershell
   Copy-Item .env.example .env
   ```

4. **Initialize & Run Database Migrations:**
   Ensure your database URL is correctly configured in `.env`, then apply the migrations:
   ```powershell
   flask db upgrade
   ```

5. **Seed Initial Company Metadata:**
   ```powershell
   python scripts/seed_metadata.py
   ```

6. **Start Flask Development Server:**
   ```powershell
   python run.py
   # Or using Flask CLI:
   flask run --debug
   ```
   The backend API will be live at `http://localhost:5000/api/v1/`.

---

### 2. Frontend Setup

1. **Navigate to the frontend directory:**
   ```powershell
   cd frontend
   ```

2. **Install Node packages:**
   ```powershell
   npm install
   ```

3. **Configure Environment Variables:**
   Copy `frontend/.env.example` to `frontend/.env` and paste your Supabase URL and Anon key:
   ```powershell
   Copy-Item .env.example .env
   ```

4. **Start Vite Development Server:**
   ```powershell
   npm run dev
   ```
   The frontend will be accessible at `http://localhost:5173/` (or the port specified by Vite in your console).

---

## Price Ingestion Pipeline

To fetch the latest end-of-day (EOD) prices for Pakistan Stock Exchange equities, the project contains a price ingestion service.

### Trigger Ingestion via CLI
You can ingest prices from the `backend/` directory using the Python command-line utility:
```powershell
cd backend

# Ingest last 30 days of data for the default set of tickers
python scripts/ingest_prices.py

# Ingest specific tickers for the last 7 days
python scripts/ingest_prices.py --tickers ENGRO HUBC LUCK --days 7

# Perform a dry-run (won't save to the database)
python scripts/ingest_prices.py --dry-run
```

---

## Running Tests

We use `pytest` for the backend testing suite. The tests automatically initialize a fast, in-memory SQLite database, meaning no network or external database credentials are required to run them.

Run tests from the `backend/` directory:
```powershell
cd backend
pytest tests/ -v
```

---

## Guidelines for Team Collaboration

1. **Never Commit Secrets**: Do not commit local `.env` files (e.g. `backend/.env` or `frontend/.env`). Both are ignored in the root `.gitignore`. Always document any new variables in `.env.example` and `frontend/.env.example`.
2. **Database Schema Changes**: Do not modify models without creating corresponding database migrations. Navigate to `backend/` and run `flask db migrate -m "Description"` to generate a new migration file, review it, and then commit it.
3. **Pull Requests**: Ensure all backend unit tests pass before requesting reviews on pull requests.