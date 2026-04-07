"""
ListingPilot Backend
AI-powered e-commerce listing generator.
With user management + LemonSqueezy payment integration.
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

LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://your-app.vercel.app",
).split(",")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="ListingPilot API", version="0.2.0")

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
    """Extract and validate user from Bearer token."""
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
    credential: str  # Google ID token from frontend


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
    """Register a new user."""
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
    """Login with email and password."""
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
    """Get current user info and usage."""
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
    """
    Login or register with Google.
    Frontend sends the credential (ID token) from Google Sign-In.
    Backend verifies it with Google and creates/finds the user.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google login not configured")

    # Verify the Google ID token
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={req.credential}"
        )

    if resp.status_code != 200:
        raise HTTPException(401, "Invalid Google token")

    google_data = resp.json()

    # Verify the token was issued for our app
    if google_data.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Token not issued for this application")

    email = google_data.get("email", "").lower().strip()
    if not email:
        raise HTTPException(401, "No email in Google token")

    # Find or create user
    user = get_user_by_email(email)
    if not user:
        # Create user with a random password (they'll use Google to login)
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
# LemonSqueezy Webhook
# ---------------------------------------------------------------------------
def verify_ls_signature(payload: bytes, signature: str) -> bool:
    """Verify LemonSqueezy webhook signature."""
    if not LEMONSQUEEZY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="x-signature"),
):
    """
    Handle LemonSqueezy subscription events.

    Events:
    - subscription_created  -> upgrade to pro
    - subscription_updated  -> check status, upgrade or downgrade
    - subscription_cancelled / subscription_expired -> downgrade to free

    Setup in LemonSqueezy dashboard:
    1. Go to Settings -> Webhooks -> Add Endpoint
    2. URL: https://api.yourdomain.com/webhook/lemonsqueezy
    3. Select events: subscription_created, subscription_updated,
       subscription_cancelled, subscription_expired
    4. Copy signing secret to .env LEMONSQUEEZY_WEBHOOK_SECRET

    When creating checkout link, pass user email as custom data:
    https://yourstore.lemonsqueezy.com/checkout/buy/xxx?checkout[custom][user_email]=user@example.com
    """
    body = await request.body()

    # Verify signature in production
    if LEMONSQUEEZY_WEBHOOK_SECRET:
        if not x_signature or not verify_ls_signature(body, x_signature):
            raise HTTPException(403, "Invalid signature")

    data = json.loads(body)
    event_name = data.get("meta", {}).get("event_name", "")
    attrs = data.get("data", {}).get("attributes", {})

    # Get user email from custom data (passed during checkout)
    custom = data.get("meta", {}).get("custom_data", {})
    user_email = custom.get("user_email", "").lower().strip()

    if not user_email:
        user_email = attrs.get("user_email", "").lower().strip()

    if not user_email:
        return {"status": "skipped", "reason": "no user_email"}

    customer_id = str(data.get("data", {}).get("id", ""))
    subscription_id = str(attrs.get("subscription_id", attrs.get("id", "")))
    status = attrs.get("status", "")

    if event_name in ("subscription_created", "subscription_updated"):
        if status in ("active", "on_trial"):
            update_user_plan(user_email, "pro", customer_id, subscription_id)
            return {"status": "upgraded", "email": user_email}
        if status in ("cancelled", "expired", "past_due", "unpaid"):
            update_user_plan(user_email, "free", customer_id, subscription_id)
            return {"status": "downgraded", "email": user_email}

    elif event_name in ("subscription_cancelled", "subscription_expired"):
        update_user_plan(user_email, "free", customer_id, subscription_id)
        return {"status": "downgraded", "email": user_email}

    return {"status": "ignored", "event": event_name}


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
    """Generate product listings. Requires authentication."""
    user = await get_current_user(authorization)

    # Check usage limit
    daily_limit = PRO_DAILY_LIMIT if user["plan"] == "pro" else FREE_DAILY_LIMIT
    used = get_daily_usage(user["id"])
    if used >= daily_limit:
        msg = (
            "Daily limit reached. Upgrade to Pro for more generations."
            if user["plan"] == "free"
            else "Daily limit reached. Resets at midnight UTC."
        )
        raise HTTPException(429, detail={"message": msg, "remaining": 0})

    # Validate & generate
    platforms = req.validate_platforms()
    tasks = [
        generate_for_platform(p, req.product_name, req.features, req.audience or "", req.tone)
        for p in platforms
    ]
    results = await asyncio.gather(*tasks)

    # Consume usage
    new_count = increment_usage(user["id"])
    remaining = max(daily_limit - new_count, 0)

    return GenerateResponse(results=list(results), remaining=remaining)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


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
