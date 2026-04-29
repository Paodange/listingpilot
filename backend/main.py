"""
ListingPilot Backend
AI-powered e-commerce listing generator with DodoPayments subscription support.
"""

import asyncio
import base64
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

# DodoPayments
DODOPAYMENTS_API_KEY       = os.getenv("DODOPAYMENTS_API_KEY", "")
DODOPAYMENTS_WEBHOOK_SECRET = os.getenv("DODOPAYMENTS_WEBHOOK_SECRET", "")
DODOPAYMENTS_CHECKOUT_URL  = os.getenv("DODOPAYMENTS_CHECKOUT_URL", "")  # payment link from dashboard

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
# DodoPayments Webhook
# ---------------------------------------------------------------------------
def _verify_dodo_signature(
    payload: bytes,
    webhook_id: str,
    webhook_timestamp: str,
    webhook_signature: str,
    secret: str,
) -> bool:
    """
    Verify DodoPayments webhook using Svix-style HMAC-SHA256.
    Signature header format: "v1,<base64(hmac)>" (space-separated for multiple)
    Secret is base64-encoded (strip "whsec_" prefix if present).
    """
    raw_secret = secret.removeprefix("whsec_")
    try:
        key_bytes = base64.b64decode(raw_secret)
    except Exception:
        key_bytes = raw_secret.encode()

    msg = f"{webhook_id}.{webhook_timestamp}.{payload.decode()}"
    digest = hmac.new(key_bytes, msg.encode(), hashlib.sha256).digest()
    expected = f"v1,{base64.b64encode(digest).decode()}"

    return any(
        hmac.compare_digest(expected, sig.strip())
        for sig in webhook_signature.split(" ")
    )


@app.post("/webhook/dodopayments")
async def dodo_webhook(
    request: Request,
    webhook_id: Optional[str] = Header(None, alias="webhook-id"),
    webhook_timestamp: Optional[str] = Header(None, alias="webhook-timestamp"),
    webhook_signature: Optional[str] = Header(None, alias="webhook-signature"),
):
    """
    Handle DodoPayments subscription lifecycle events.

    Events handled:
      subscription.active    → upgrade user to pro
      subscription.cancelled → downgrade to free
      subscription.expired   → downgrade to free
      subscription.on_hold   → downgrade to free (payment failed)

    Setup in DodoPayments dashboard:
      1. Developers → Webhooks → Add Endpoint
      2. URL: https://apicore.ntotech.top/webhook/dodopayments
      3. Select all subscription.* events
      4. Copy the signing secret to .env DODOPAYMENTS_WEBHOOK_SECRET

    The customer email must be passed as metadata when creating the checkout
    session so we can look up the user here.
    """
    if not DODOPAYMENTS_WEBHOOK_SECRET:
        raise HTTPException(500, "DodoPayments webhook secret not configured")

    body = await request.body()

    if not webhook_id or not webhook_timestamp or not webhook_signature:
        raise HTTPException(400, "Missing webhook signature headers")

    if not _verify_dodo_signature(
        body, webhook_id, webhook_timestamp, webhook_signature, DODOPAYMENTS_WEBHOOK_SECRET
    ):
        raise HTTPException(403, "Invalid webhook signature")

    data = json.loads(body)
    event_type = data.get("type", "")

    # DodoPayments payload structure:
    # { "type": "subscription.active", "data": { "payload": { ... } } }
    payload = data.get("data", {}).get("payload", {})
    subscription_id = payload.get("subscription_id", "")

    # Extract customer email — try common field paths
    customer = payload.get("customer", {})
    user_email = (
        customer.get("email")
        or payload.get("customer_email")
        or payload.get("email")
        or ""
    ).lower().strip()

    if not user_email:
        return {"status": "skipped", "reason": "no customer email in payload"}

    if not get_user_by_email(user_email):
        return {"status": "skipped", "reason": "user not found"}

    if event_type == "subscription.active":
        update_user_plan(user_email, "pro", dp_subscription_id=subscription_id)
        return {"status": "upgraded", "email": user_email}

    if event_type in ("subscription.cancelled", "subscription.expired", "subscription.on_hold"):
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
        "payment_provider": "dodopayments",
        "checkout_url": DODOPAYMENTS_CHECKOUT_URL,
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
