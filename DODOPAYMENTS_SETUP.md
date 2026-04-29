# DodoPayments Setup Guide — ListingPilot

Complete walkthrough for registering, setting up a subscription product, passing platform review, and wiring the webhook.

---

## Part 1 — Register and Verify Your Account

### 1.1 Sign Up

1. Go to **https://dodopayments.com** and click **Get Started**.
2. Enter your email and create a password.
3. Verify your email address from the confirmation link.

### 1.2 Business Verification (KYC)

DodoPayments requires identity and business verification before you can receive payments. Prepare the following:

**Personal Information:**
| Field | Your Value |
|-------|-----------|
| Full Name | Depeng Liu |
| Country | (your country of residence) |
| ID Type | Passport or national ID |

**Business Information:**
| Field | Your Value |
|-------|-----------|
| Business Type | Individual / Sole Proprietor |
| Business Name | ListingPilot (or "Depeng Liu") |
| Website URL | https://cc.ntotech.top |
| Business Category | Software / SaaS |
| Product Description | See Part 2 below |

**Bank Account:**
- Have your bank account details ready (account number, routing/SWIFT number) for payout setup.

---

## Part 2 — Content for Platform Review

Use these exact descriptions when filling out the DodoPayments application form.

### Business / Product Description

> **ListingPilot** is an AI-powered SaaS tool that helps e-commerce sellers generate optimized product listings for multiple platforms (Amazon, Shopify, Etsy, eBay) from a single input. Sellers enter their product name, key features, and target audience, and the tool produces platform-specific titles, bullet points, descriptions, and SEO metadata using the DeepSeek AI API.
>
> Users register for a free account with 3 generations per day. A Pro subscription ($5/month) increases the daily limit to 100 generations. Payment is processed through DodoPayments with automatic subscription management via webhooks.

### Refund Policy (add this to your website footer or /terms page)

> **Refund Policy**
>
> We offer a full refund within 7 days of your initial Pro subscription charge if you are not satisfied. After 7 days, subscriptions are non-refundable but you can cancel at any time to stop future charges. To request a refund, email support@ntotech.top with your registered email address.

### Terms of Service URL

Before going live, publish a Terms of Service page at **https://cc.ntotech.top/terms** that covers:
- Service description
- User accounts and eligibility
- Subscription and billing
- Acceptable use (no scraping, no spam)
- Limitation of liability
- Governing law

> Tip: Use a generator like https://www.termsfeed.com/terms-of-service-generator/ to create an initial draft, then customize it.

### Privacy Policy URL

Publish a Privacy Policy at **https://cc.ntotech.top/privacy** that covers:
- What data you collect (email, usage logs)
- How you use it (authentication, usage tracking)
- Third-party services (DeepSeek API, DodoPayments)
- Data retention and deletion
- GDPR/CCPA rights if applicable

---

## Part 3 — Create a Subscription Product

1. In the DodoPayments dashboard, go to **Products → Add Product**.
2. Fill in:
   - **Product Name:** ListingPilot Pro
   - **Description:** 100 AI-generated product listings per day across Amazon, Shopify, Etsy, and eBay. Cancel anytime.
   - **Pricing Type:** Recurring
   - **Price:** $5.00 USD
   - **Billing interval:** Monthly
3. Click **Save**.
4. Open the product you just created and click **Payment Link → Generate Link**.
5. Copy the full URL — it looks like:
   ```
   https://checkout.dodopayments.com/buy/plink_xxxxxxxxxx
   ```
6. Paste this URL into your `.env` file:
   ```
   DODOPAYMENTS_CHECKOUT_URL=https://checkout.dodopayments.com/buy/plink_xxxxxxxxxx
   ```

---

## Part 4 — Set Up the Webhook

### 4.1 Add the Endpoint

1. In the dashboard go to **Developers → Webhooks → Add Endpoint**.
2. Set the URL to:
   ```
   https://apicore.ntotech.top/webhook/dodopayments
   ```
3. Select these events:
   - `subscription.active`
   - `subscription.cancelled`
   - `subscription.expired`
   - `subscription.on_hold`
4. Click **Save**.

### 4.2 Copy the Signing Secret

1. After saving, open the webhook endpoint you just created.
2. Click **Reveal Signing Secret** (or similar button).
3. Copy the full secret — it starts with `whsec_`.
4. Paste it into your `.env` file:
   ```
   DODOPAYMENTS_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

### 4.3 Test the Webhook Locally (before deploying)

Use [ngrok](https://ngrok.com) to expose your local server temporarily:
```bash
# Start your backend
cd backend && python main.py

# In a new terminal, expose it
ngrok http 8000
```
Temporarily set your webhook URL in DodoPayments to the ngrok URL (e.g., `https://abc123.ngrok.io/webhook/dodopayments`), then use the **Send Test Event** button in the dashboard to confirm your backend receives and processes it correctly.

---

## Part 5 — Get Your API Key

1. Go to **Developers → API Keys → Create Key**.
2. Give it a name (e.g., "ListingPilot Production").
3. Copy the key and add it to `.env`:
   ```
   DODOPAYMENTS_API_KEY=dp_live_xxxxxxxxxxxxxxxx
   ```

> The API key is currently used for future features (subscription status checks, customer portal). The webhook alone handles plan upgrades/downgrades.

---

## Part 6 — Final .env Checklist

Your `backend/.env` should look like this before going live:

```env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat

JWT_SECRET=<72-char random hex — run: python -c "import secrets; print(secrets.token_hex(36))">
TOKEN_EXPIRE_HOURS=72

FREE_DAILY_LIMIT=3
PRO_DAILY_LIMIT=100

GOOGLE_CLIENT_ID=343640572950-...apps.googleusercontent.com

DODOPAYMENTS_API_KEY=dp_live_...
DODOPAYMENTS_WEBHOOK_SECRET=whsec_...
DODOPAYMENTS_CHECKOUT_URL=https://checkout.dodopayments.com/buy/plink_...

PORT=8000
ALLOWED_ORIGINS=https://cc.ntotech.top
```

---

## Part 7 — Install Updated Dependencies

After pulling these changes, run:

```bash
source .venv/Scripts/activate   # Windows Git Bash
cd backend
pip install -r requirements.txt
```

The new `bcrypt` package will be installed. **Note:** Any existing user accounts created before this update used SHA-256 password hashing — those users will need to re-register or reset their password. Since the app is pre-launch with no real users yet, this is safe to do.

---

## Part 8 — Payment Flow Summary

```
User clicks "Upgrade — $5/mo"
        ↓
Redirect to DodoPayments hosted checkout
(email pre-filled via ?customer_email=...)
        ↓
User enters card details and subscribes
        ↓
DodoPayments sends POST /webhook/dodopayments
with event type "subscription.active"
        ↓
Backend verifies signature, finds user by email,
sets plan = "pro"
        ↓
Next time user refreshes, /auth/me returns plan: "pro"
and the Pro badge appears
```

Cancellation flows the same way: DodoPayments sends `subscription.cancelled` → backend sets plan back to `free`.
