"""
ListingPilot Backend
AI-powered e-commerce listing generator with Creem subscription support.
"""

import asyncio
import hashlib
import hmac
import json
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import create_token, decode_token, hash_password, verify_password
from database import (
    create_user,
    get_daily_usage,
    get_user_by_email,
    get_user_by_id,
    increment_usage,
    update_user_plan,
)
from prompts import PLATFORM_PROMPT_BUILDERS, get_system_prompt

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "3"))
PRO_DAILY_LIMIT = int(os.getenv("PRO_DAILY_LIMIT", "100"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# Creem
CREEM_API_KEY        = os.getenv("CREEM_API_KEY", "")
CREEM_WEBHOOK_SECRET = os.getenv("CREEM_WEBHOOK_SECRET", "")
CREEM_CHECKOUT_URL   = os.getenv("CREEM_CHECKOUT_URL", "")  # payment link from Creem dashboard
CREEM_TEST_MODE      = os.getenv("CREEM_TEST_MODE", "false").lower() == "true"

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://cc.ntotech.top",
).split(",")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="ListingPilot API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Token expired or invalid")
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    return user


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str = Field(..., examples=["seller@example.com"])
    password: str = Field(..., min_length=6, examples=["securepass123"])


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class GenerateRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    features: str = Field(..., min_length=1, max_length=2000)
    audience: Optional[str] = Field("", max_length=500)
    platforms: list[str] = Field(..., min_length=1)
    tone: str = Field("professional")

    def validate_platforms(self) -> list[str]:
        valid = set(PLATFORM_PROMPT_BUILDERS.keys())
        result = [p for p in self.platforms if p in valid]
        if not result:
            raise HTTPException(400, f"No valid platforms. Choose from: {', '.join(valid)}")
        return result


class PlatformResult(BaseModel):
    platform: str
    data: dict
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    results: list[PlatformResult]
    remaining: int


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------
@app.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    email = req.email.lower().strip()
    if get_user_by_email(email):
        raise HTTPException(409, "Email already registered")
    hashed = hash_password(req.password)
    user = create_user(email, hashed)
    if not user:
        raise HTTPException(500, "Failed to create user")
    token = create_token(user["id"], user["email"])
    return AuthResponse(
        token=token,
        user={"id": user["id"], "email": user["email"], "plan": user["plan"]},
    )


@app.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    email = req.email.lower().strip()
    user = get_user_by_email(email)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], user["email"])
    return AuthResponse(
        token=token,
        user={"id": user["id"], "email": user["email"], "plan": user["plan"]},
    )


@app.get("/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    daily_limit = PRO_DAILY_LIMIT if user["plan"] == "pro" else FREE_DAILY_LIMIT
    used = get_daily_usage(user["id"])
    return {
        "id": user["id"],
        "email": user["email"],
        "plan": user["plan"],
        "usage": {
            "used": used,
            "limit": daily_limit,
            "remaining": max(daily_limit - used, 0),
        },
    }


@app.post("/auth/google", response_model=AuthResponse)
async def google_login(req: GoogleLoginRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google login not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={req.credential}"
        )
    if resp.status_code != 200:
        raise HTTPException(401, "Invalid Google token")

    google_data = resp.json()
    if google_data.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Token not issued for this application")

    email = google_data.get("email", "").lower().strip()
    if not email:
        raise HTTPException(401, "No email in Google token")

    user = get_user_by_email(email)
    if not user:
        random_pw = hash_password(os.urandom(32).hex())
        user = create_user(email, random_pw)
        if not user:
            raise HTTPException(500, "Failed to create user")

    token = create_token(user["id"], user["email"])
    return AuthResponse(
        token=token,
        user={"id": user["id"], "email": user["email"], "plan": user["plan"]},
    )


# ---------------------------------------------------------------------------
# Creem Webhook
# ---------------------------------------------------------------------------
def _verify_creem_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Creem webhook using HMAC-SHA256.
    Header `creem-signature` contains the hex digest of HMAC-SHA256(secret, raw_body).
    """
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature.strip())


@app.post("/webhook/creem")
async def creem_webhook(
    request: Request,
    creem_signature: Optional[str] = Header(None, alias="creem-signature"),
):
    """
    Handle Creem subscription lifecycle events.

    Events handled:
      checkout.completed     → upgrade user to pro
      subscription.active    → upgrade user to pro
      subscription.paid      → keep user on pro (renewal)
      subscription.canceled  → downgrade to free
      subscription.expired   → downgrade to free

    Setup in Creem dashboard:
      1. Developers → Webhooks → Add Endpoint
      2. URL: https://apicore.ntotech.top/webhook/creem
      3. Subscribe to checkout.completed + all subscription.* events
      4. Copy the signing secret to .env CREEM_WEBHOOK_SECRET

    Creem checkout link should pass `?email=<user_email>` so the customer
    object on the webhook contains the email we use to look up the user.
    """
    if not CREEM_WEBHOOK_SECRET:
        raise HTTPException(500, "Creem webhook secret not configured")

    body = await request.body()

    if not creem_signature:
        raise HTTPException(400, "Missing creem-signature header")

    if not _verify_creem_signature(body, creem_signature, CREEM_WEBHOOK_SECRET):
        raise HTTPException(403, "Invalid webhook signature")

    data = json.loads(body)
    event_type = data.get("eventType") or data.get("event_type") or ""

    # Creem payload: { "id": "evt_x", "eventType": "...", "object": { ... } }
    obj = data.get("object", {}) or data.get("data", {})
    subscription_id = (
        obj.get("subscription_id")
        or (obj.get("subscription") or {}).get("id")
        or (obj.get("id") if event_type.startswith("subscription.") else "")
        or ""
    )

    customer = obj.get("customer") or {}
    user_email = (
        (customer.get("email") if isinstance(customer, dict) else "")
        or obj.get("customer_email")
        or obj.get("email")
        or ""
    ).lower().strip()

    if not user_email:
        return {"status": "skipped", "reason": "no customer email in payload"}

    if not get_user_by_email(user_email):
        return {"status": "skipped", "reason": "user not found"}

    if event_type in ("checkout.completed", "subscription.active", "subscription.paid"):
        update_user_plan(user_email, "pro", subscription_id=subscription_id)
        return {"status": "upgraded", "email": user_email}

    if event_type in ("subscription.canceled", "subscription.cancelled", "subscription.expired"):
        update_user_plan(user_email, "free")
        return {"status": "downgraded", "email": user_email}

    return {"status": "ignored", "event_type": event_type}


# ---------------------------------------------------------------------------
# DeepSeek API
# ---------------------------------------------------------------------------
async def call_deepseek(system_prompt: str, user_prompt: str) -> dict:
    if not DEEPSEEK_API_KEY:
        raise HTTPException(500, "DEEPSEEK_API_KEY not configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"DeepSeek API error: {resp.status_code}")

    body = resp.json()
    content = body["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]

    return json.loads(content)


async def generate_for_platform(
    platform: str, product_name: str, features: str, audience: str, tone: str,
) -> PlatformResult:
    prompt_builder = PLATFORM_PROMPT_BUILDERS[platform]
    user_prompt = prompt_builder(product_name, features, audience, tone)
    system_prompt = get_system_prompt()
    try:
        data = await call_deepseek(system_prompt, user_prompt)
        return PlatformResult(platform=platform, data=data)
    except json.JSONDecodeError:
        return PlatformResult(platform=platform, data={}, error="Failed to parse AI response")
    except HTTPException:
        raise
    except Exception as e:
        return PlatformResult(platform=platform, data={}, error=str(e))


# ---------------------------------------------------------------------------
# Generate Route (requires auth)
# ---------------------------------------------------------------------------
@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)

    daily_limit = PRO_DAILY_LIMIT if user["plan"] == "pro" else FREE_DAILY_LIMIT
    used = get_daily_usage(user["id"])
    if used >= daily_limit:
        msg = (
            "Daily limit reached. Upgrade to Pro for more generations."
            if user["plan"] == "free"
            else "Daily limit reached. Resets at midnight UTC."
        )
        raise HTTPException(429, detail={"message": msg, "remaining": 0})

    platforms = req.validate_platforms()
    tasks = [
        generate_for_platform(p, req.product_name, req.features, req.audience or "", req.tone)
        for p in platforms
    ]
    results = await asyncio.gather(*tasks)

    new_count = increment_usage(user["id"])
    remaining = max(daily_limit - new_count, 0)

    return GenerateResponse(results=list(results), remaining=remaining)


# ---------------------------------------------------------------------------
# Config (public — used by frontend)
# ---------------------------------------------------------------------------
@app.get("/config")
async def get_config():
    """Return payment provider info for the frontend."""
    return {
        "payment_provider": "creem",
        "checkout_url": CREEM_CHECKOUT_URL,
        "test_mode": CREEM_TEST_MODE,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
