from __future__ import annotations

import os

from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError
from pydantic import BaseModel, EmailStr, Field, ConfigDict, constr
from supabase import Client, create_client

load_dotenv()



STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
DASHBOARD_FILE = STATIC_DIR / "dashboard.html"
KYC_TABLE = os.getenv("SUPABASE_KYC_TABLE", "kyc_profiles")


class SignupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: constr(strip_whitespace=True, min_length=3, max_length=30) = Field(...)
    password: constr(min_length=8) = Field(...)
    email: EmailStr
    phone_number: constr(strip_whitespace=True, min_length=7, max_length=20)
    address: constr(strip_whitespace=True, min_length=5, max_length=120)
    industry: str
    profession: str
    credit_card: Optional[constr(strip_whitespace=True, min_length=4, max_length=32)] = None


class LoginForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: constr(strip_whitespace=True, min_length=3, max_length=30)
    password: constr(min_length=8)


def build_supabase_client() -> Client:
    """
    Build a Supabase client from environment variables.
    Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or anon key in dev) are set.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Supabase credentials missing. Please set SUPABASE_URL and SUPABASE_KEY."
        )

    return create_client(supabase_url, supabase_key)


class SupabaseService:
    def __init__(self, client: Client):
        self.client = client

    def signup(self, payload: SignupForm) -> Dict[str, Any]:
        # Attempt to create a Supabase auth user (Supabase handles password hashing).
        try:
            auth_response = self.client.auth.sign_up(
                {
                    "email": payload.email,
                    "password": payload.password,
                    "options": {
                        "data": {
                            "username": payload.username,
                            "phone_number": payload.phone_number,
                        }
                    },
                }
            )
        except AuthApiError as exc:
            detail = getattr(exc, "message", str(exc))
            if "User already registered" in detail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ser already registered. Try logging in instead.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Supabase auth error: {detail}",
            ) from exc

        if not auth_response or not getattr(auth_response, "user", None):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to create user in Supabase auth. Check credentials and try again.",
            )

        user_id = auth_response.user.id
        profile_payload = {
            "auth_user_id": user_id,
            "username": payload.username,
            "email": payload.email,
            "phone_number": payload.phone_number,
            "address": payload.address,
            "industry": payload.industry,
            "profession": payload.profession,
            "credit_card": payload.credit_card,
        }

        try:
            db_response = self.client.table(KYC_TABLE).insert(profile_payload).execute()
        except APIError as exc:
            # Common when RLS blocks inserts or schema mismatches.
            if getattr(exc, "code", "") == "42501":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Supabase rejected the profile insert because of row-level security. "
                        "Use a service role key or relax the RLS policy for the KYC table."
                    ),
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save KYC profile: {getattr(exc, 'message', str(exc))}",
            ) from exc

        if getattr(db_response, "error", None):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save KYC profile: {db_response.error.get('message')}",
            )

        return {"user_id": user_id}

    def login(self, payload: LoginForm) -> Dict[str, Any]:
        try:
            # Lookup email by username.
            profile_response = (
                self.client.table(KYC_TABLE)
                .select("email")
                .eq("username", payload.username)
                .limit(1)
                .execute()
            )

            profile_data = getattr(profile_response, "data", [])
            if not profile_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password.",
                )

            email = profile_data[0]["email"]

            try:
                auth_response = self.client.auth.sign_in_with_password(
                    {"email": email, "password": payload.password}
                )
            except AuthApiError as exc:
                detail = getattr(exc, "message", str(exc))
                # Supabase / GoTrue typically uses this wording for unconfirmed emails.
                if "Email not confirmed" in detail or "email_not_confirmed" in detail:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Please confirm your email before logging in.",
                    ) from exc
                # Any other auth error should behave like invalid credentials.
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password.",
                ) from exc

            if not auth_response or not getattr(auth_response, "user", None):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password.",
                )

            return {"redirect_to": "/dashboard"}
        except HTTPException:
            # Let explicit HTTP errors bubble up as-is.
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            # Catch-all for any unexpected issues so the client sees a generic message.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something went wrong. Please try again.",
            ) from exc


app = FastAPI(title="PanelPrompt Auth API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_supabase_service() -> SupabaseService:
    client = build_supabase_client()
    return SupabaseService(client)


@app.post("/api/signup")
def signup_user(payload: SignupForm, service: SupabaseService = Depends(get_supabase_service)):
    result = service.signup(payload)
    return {"message": "Account created successfully. We have sent a confirmation email to your inbox. Please check your email and follow the instructions to complete your signup and log in.", **result}


@app.post("/api/login")
def login_user(payload: LoginForm, service: SupabaseService = Depends(get_supabase_service)):
    result = service.login(payload)
    return {"message": "Login successful.", **result}


@app.post("/api/logout")
def logout_user():
   
    return {"message": "Logged out successfully.", "redirect_to": "/"}


@app.get("/", response_class=HTMLResponse)
def serve_index():
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend not found. Please ensure static/index.html exists.",
        )
    return INDEX_FILE.read_text(encoding="utf-8")


@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    if not DASHBOARD_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found. Please ensure static/dashboard.html exists.",
        )
    return DASHBOARD_FILE.read_text(encoding="utf-8")


@app.get("/healthz")
def health_check():
    return {"status": "ok"}
