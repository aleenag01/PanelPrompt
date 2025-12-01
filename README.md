## PanelPrompt Auth Portal

This repo now hosts a FastAPI backend plus a responsive HTML/JS frontend that
handles login and signup through Supabase authentication and a Supabase table
for KYC data.

### 1. Prerequisites

- Python 3.11+ (project targets 3.13 in `pyproject.toml`)
- A Supabase project with:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` (preferred for server-side usage)
  - a `kyc_profiles` table (default name) that includes:
    - `auth_user_id uuid primary key`
    - `username text unique`
    - `email text`
    - `phone_number text`
    - `address text`
    - `industry text`
    - `profession text`
    - `credit_card text null`

Set the table name via `SUPABASE_KYC_TABLE` if you use something else.

### 2. Environment variables

Create a `.env` file in the repo root:

```
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=service-role-key
# Optional: use anon key for local dev only
# SUPABASE_ANON_KEY=anon-public-key
# Optional: override default table name
# SUPABASE_KYC_TABLE=kyc_profiles
```

The backend automatically loads this file via `python-dotenv`.

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Run the stack

```
uvicorn main:app --reload
```

Visit `http://localhost:8000` for the login/sign-up UI. Successful logins
redirect to `/dashboard`.

### 5. Customizing

- Update `static/index.html`, `static/styles.css`, and `static/app.js` to match
  your brand.
- The dummy lists for *Industry* and *Profession* live in `static/app.js`.
- API endpoints are defined in `main.py`:
  - `POST /api/signup`
  - `POST /api/login`
  - `GET /dashboard` (placeholder view)

Remember to add real Supabase Row Level Security policies and token validation
before shipping to production. The current dashboard endpoint is intentionally
open for demo purposes.
