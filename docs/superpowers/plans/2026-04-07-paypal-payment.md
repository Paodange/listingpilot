# PayPal Payment Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留 LemonSqueezy 的基础上，新增 PayPal 订阅支付，通过 `PAYMENT_PROVIDER` 环境变量单一激活其中一种。

**Architecture:** 后端新增 `/config`、`/paypal/capture`、`/webhook/paypal` 三个接口；数据库加 `pp_subscription_id` 字段；前端按 `/config` 返回的 provider 动态加载 PayPal SDK 或沿用 LemonSqueezy 链接。

**Tech Stack:** Python/FastAPI, httpx, SQLite, React (inline CSS, no router), PayPal JS SDK v2

---

## File Map

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/database.py` | 修改 | 新增 `pp_subscription_id` 列，更新 `update_user_plan()` |
| `backend/main.py` | 修改 | 新增 PayPal 环境变量、`/config`、`/paypal/capture`、`/webhook/paypal` |
| `backend/.env` | 修改 | 新增 PayPal 相关变量 |
| `frontend/listing-pilot/src/App.jsx` | 修改 | 启动时读 `/config`，条件渲染 PayPal 按钮或 LS 链接 |

---

## Task 1: 数据库 — 新增 pp_subscription_id 字段

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: 在 `init_db()` 的 `CREATE TABLE` 语句中新增字段，并添加迁移语句**

打开 [backend/database.py](backend/database.py)，将 `init_db()` 函数替换为：

```python
def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                email                TEXT UNIQUE NOT NULL,
                password             TEXT NOT NULL,
                plan                 TEXT NOT NULL DEFAULT 'free',
                ls_customer_id       TEXT DEFAULT '',
                ls_subscription_id   TEXT DEFAULT '',
                pp_subscription_id   TEXT DEFAULT '',
                created_at           REAL NOT NULL,
                updated_at           REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                date        TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # Migrate: add pp_subscription_id if missing (safe to run on existing DB)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "pp_subscription_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN pp_subscription_id TEXT DEFAULT ''")
```

- [ ] **Step 2: 更新 `update_user_plan()` 支持 provider 参数**

将现有的 `update_user_plan()` 函数替换为：

```python
def update_user_plan(
    email: str,
    plan: str,
    ls_customer_id: str = "",
    ls_subscription_id: str = "",
    pp_subscription_id: str = "",
):
    now = time.time()
    with get_db() as conn:
        conn.execute(
            """UPDATE users
               SET plan=?, ls_customer_id=?, ls_subscription_id=?,
                   pp_subscription_id=?, updated_at=?
               WHERE email=?""",
            (plan, ls_customer_id, ls_subscription_id, pp_subscription_id, now, email),
        )
```

- [ ] **Step 3: 启动后端验证迁移是否生效**

```bash
cd backend
python -c "from database import init_db; init_db(); print('OK')"
```

Expected output: `OK`（无报错）

- [ ] **Step 4: Commit**

```bash
git add backend/database.py
git commit -m "feat: add pp_subscription_id column and update update_user_plan"
```

---

## Task 2: 后端 — 环境变量与 `/config` 接口

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/.env`

- [ ] **Step 1: 在 `main.py` 的 Config 区块新增 PayPal 配置**

在 [backend/main.py](backend/main.py) 的 `# Config` 区块（约第 36 行），在 `LEMONSQUEEZY_WEBHOOK_SECRET` 那行之后添加：

```python
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "lemonsqueezy")  # "lemonsqueezy" | "paypal"

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_PLAN_ID = os.getenv("PAYPAL_PLAN_ID", "")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_API_BASE = "https://api-m.sandbox.paypal.com"  # 上线时换成 https://api-m.paypal.com
```

- [ ] **Step 2: 新增 `/config` 接口**

在 `# Health` 路由之前新增：

```python
# ---------------------------------------------------------------------------
# Config (public — used by frontend to determine payment provider)
# ---------------------------------------------------------------------------
@app.get("/config")
async def get_config():
    """Return active payment provider info for the frontend."""
    if PAYMENT_PROVIDER == "paypal":
        return {
            "payment_provider": "paypal",
            "paypal_client_id": PAYPAL_CLIENT_ID,
            "paypal_plan_id": PAYPAL_PLAN_ID,
        }
    # Default: lemonsqueezy
    ls_checkout = os.getenv("LEMONSQUEEZY_CHECKOUT_URL", "")
    return {
        "payment_provider": "lemonsqueezy",
        "checkout_url": ls_checkout,
    }
```

- [ ] **Step 3: 在 `.env` 中新增变量**

在 [backend/.env](backend/.env) 末尾追加：

```
# Payment provider: "lemonsqueezy" or "paypal"
PAYMENT_PROVIDER=lemonsqueezy

# LemonSqueezy checkout URL (used when PAYMENT_PROVIDER=lemonsqueezy)
LEMONSQUEEZY_CHECKOUT_URL=https://yourstore.lemonsqueezy.com/checkout/buy/your-variant-id

# PayPal (used when PAYMENT_PROVIDER=paypal)
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_PLAN_ID=
PAYPAL_WEBHOOK_ID=
```

> 注意：`LEMONSQUEEZY_CHECKOUT_URL` 把原来写死在前端的 URL 移到了后端统一管理。

- [ ] **Step 4: 启动后端，验证 `/config` 接口**

```bash
cd backend && python main.py &
curl http://localhost:8000/config
```

Expected（PAYMENT_PROVIDER=lemonsqueezy 时）:
```json
{"payment_provider":"lemonsqueezy","checkout_url":"https://yourstore..."}
```

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/.env
git commit -m "feat: add PAYMENT_PROVIDER config and /config endpoint"
```

---

## Task 3: 后端 — PayPal 工具函数（获取 Access Token + 验证订阅）

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 新增 PayPal Access Token 获取函数**

在 `# DeepSeek API` 区块之前新增以下函数：

```python
# ---------------------------------------------------------------------------
# PayPal helpers
# ---------------------------------------------------------------------------
async def paypal_get_access_token() -> str:
    """Exchange client_id + client_secret for a PayPal access token."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{PAYPAL_API_BASE}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"PayPal auth failed: {resp.status_code}")
    return resp.json()["access_token"]


async def paypal_get_subscription(subscription_id: str) -> dict:
    """Fetch subscription details from PayPal REST API."""
    token = await paypal_get_access_token()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{PAYPAL_API_BASE}/v1/billing/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"PayPal subscription fetch failed: {resp.status_code}")
    return resp.json()
```

- [ ] **Step 2: 验证函数可被导入（语法检查）**

```bash
cd backend && python -c "import main; print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add PayPal access token and subscription fetch helpers"
```

---

## Task 4: 后端 — `/paypal/capture` 接口

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 新增请求模型和路由**

在 `# Request / Response Models` 区块新增模型：

```python
class PayPalCaptureRequest(BaseModel):
    subscription_id: str
```

在 `# Config` 路由之前新增：

```python
# ---------------------------------------------------------------------------
# PayPal Capture (called by frontend after user approves subscription)
# ---------------------------------------------------------------------------
@app.post("/paypal/capture")
async def paypal_capture(
    req: PayPalCaptureRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Frontend calls this after PayPal onApprove with the subscriptionID.
    Backend verifies the subscription with PayPal and upgrades the user to pro.

    Requires user to be logged in (Bearer token).
    """
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(500, "PayPal not configured")

    user = await get_current_user(authorization)

    sub = await paypal_get_subscription(req.subscription_id)
    status = sub.get("status", "")

    if status not in ("ACTIVE", "APPROVED"):
        raise HTTPException(400, f"Subscription not active (status={status})")

    update_user_plan(
        email=user["email"],
        plan="pro",
        pp_subscription_id=req.subscription_id,
    )
    return {"status": "upgraded", "plan": "pro"}
```

- [ ] **Step 2: 验证语法**

```bash
cd backend && python -c "import main; print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: 手动测试（需要 PayPal sandbox 凭据）**

若暂无凭据，跳过此步，留待 sandbox 配置完成后验证。

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add /paypal/capture endpoint to verify and upgrade subscription"
```

---

## Task 5: 后端 — `/webhook/paypal` 接口

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 新增 PayPal webhook 签名验证函数**

在 PayPal helpers 区块追加：

```python
async def paypal_verify_webhook(
    headers: dict,
    body: bytes,
) -> bool:
    """
    Verify PayPal webhook authenticity via PayPal REST API.
    Requires PAYPAL_WEBHOOK_ID set in env.
    Docs: https://developer.paypal.com/api/webhooks/v1/#verify-webhook-signature_post
    """
    if not PAYPAL_WEBHOOK_ID:
        return False
    token = await paypal_get_access_token()
    payload = {
        "auth_algo": headers.get("paypal-auth-algo", ""),
        "cert_url": headers.get("paypal-cert-url", ""),
        "transmission_id": headers.get("paypal-transmission-id", ""),
        "transmission_sig": headers.get("paypal-transmission-sig", ""),
        "transmission_time": headers.get("paypal-transmission-time", ""),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": json.loads(body),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code != 200:
        return False
    return resp.json().get("verification_status") == "SUCCESS"
```

- [ ] **Step 2: 新增 `/webhook/paypal` 路由**

在 `/webhook/lemonsqueezy` 路由之后新增：

```python
# ---------------------------------------------------------------------------
# PayPal Webhook
# ---------------------------------------------------------------------------
@app.post("/webhook/paypal")
async def paypal_webhook(request: Request):
    """
    Handle PayPal subscription lifecycle events.

    Events handled:
    - BILLING.SUBSCRIPTION.ACTIVATED   -> upgrade to pro
    - BILLING.SUBSCRIPTION.CANCELLED   -> downgrade to free
    - BILLING.SUBSCRIPTION.EXPIRED     -> downgrade to free
    - BILLING.SUBSCRIPTION.SUSPENDED   -> downgrade to free

    Setup in PayPal Developer Dashboard:
    1. My Apps & Credentials -> your app -> Webhooks -> Add Webhook
    2. URL: https://api.yourdomain.com/webhook/paypal
    3. Select events: BILLING.SUBSCRIPTION.*
    4. Copy Webhook ID to env PAYPAL_WEBHOOK_ID

    User email is stored as custom_id on the subscription (set during
    createSubscription in the frontend SDK call).
    """
    body = await request.body()
    hdrs = dict(request.headers)

    if PAYPAL_WEBHOOK_ID:
        valid = await paypal_verify_webhook(hdrs, body)
        if not valid:
            raise HTTPException(403, "Invalid PayPal webhook signature")

    data = json.loads(body)
    event_type = data.get("event_type", "")
    resource = data.get("resource", {})

    subscription_id = resource.get("id", "")
    # custom_id holds the user's email, set during frontend createSubscription
    user_email = resource.get("custom_id", "").lower().strip()

    if not user_email:
        return {"status": "skipped", "reason": "no user email in custom_id"}

    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        update_user_plan(
            email=user_email,
            plan="pro",
            pp_subscription_id=subscription_id,
        )
        return {"status": "upgraded", "email": user_email}

    if event_type in (
        "BILLING.SUBSCRIPTION.CANCELLED",
        "BILLING.SUBSCRIPTION.EXPIRED",
        "BILLING.SUBSCRIPTION.SUSPENDED",
    ):
        update_user_plan(email=user_email, plan="free")
        return {"status": "downgraded", "email": user_email}

    return {"status": "ignored", "event_type": event_type}
```

- [ ] **Step 3: 验证语法**

```bash
cd backend && python -c "import main; print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add /webhook/paypal endpoint for subscription lifecycle events"
```

---

## Task 6: 前端 — 读取 `/config`，条件渲染升级按钮

**Files:**
- Modify: `frontend/listing-pilot/src/App.jsx`

- [ ] **Step 1: 删除写死的 LEMONSQUEEZY_CHECKOUT 常量**

在 [frontend/listing-pilot/src/App.jsx](frontend/listing-pilot/src/App.jsx) 中，删除第 10 行：

```js
// 删除这行：
const LEMONSQUEEZY_CHECKOUT = "https://yourstore.lemonsqueezy.com/checkout/buy/your-variant-id";
```

- [ ] **Step 2: 在 `MainApp` 组件中新增 config state 并在 mount 时拉取**

在 `MainApp` 函数内，`const [user, setUser] = useState(initUser);` 之后新增：

```js
const [paymentConfig, setPaymentConfig] = useState(null);

useEffect(() => {
  api("/config").then(setPaymentConfig).catch(() => {});
}, []);
```

- [ ] **Step 3: 删除旧的 upgradeUrl 计算行**

删除：
```js
const upgradeUrl = `${LEMONSQUEEZY_CHECKOUT}?checkout[custom][user_email]=${encodeURIComponent(user.email)}`;
```

- [ ] **Step 4: 新增 PayPal SDK 加载 hook**

在 `MainApp` 内（paymentConfig state 之后）新增：

```js
// Load PayPal SDK when provider is paypal
useEffect(() => {
  if (!paymentConfig || paymentConfig.payment_provider !== "paypal") return;
  if (document.getElementById("paypal-sdk")) return;
  const script = document.createElement("script");
  script.id = "paypal-sdk";
  script.src = `https://www.paypal.com/sdk/js?client-id=${paymentConfig.paypal_client_id}&vault=true&intent=subscription`;
  script.async = true;
  document.head.appendChild(script);
}, [paymentConfig]);
```

- [ ] **Step 5: 新增 PayPal 按钮渲染 hook**

```js
// Render PayPal subscription button
useEffect(() => {
  if (!paymentConfig || paymentConfig.payment_provider !== "paypal") return;
  if (user.plan !== "free") return;
  const container = document.getElementById("paypal-upgrade-btn");
  if (!container) return;

  const tryRender = () => {
    if (!window.paypal) { setTimeout(tryRender, 300); return; }
    container.innerHTML = "";
    window.paypal.Buttons({
      style: { shape: "rect", color: "blue", layout: "horizontal", label: "subscribe" },
      createSubscription: (_data, actions) =>
        actions.subscription.create({
          plan_id: paymentConfig.paypal_plan_id,
          custom_id: user.email,  // used by webhook to identify user
        }),
      onApprove: async (data) => {
        try {
          await api("/paypal/capture", {
            method: "POST",
            token,
            body: { subscription_id: data.subscriptionID },
          });
          await fetchUsage();  // refresh plan + usage
        } catch (e) {
          alert("PayPal 订阅确认失败：" + e.message);
        }
      },
      onError: (err) => {
        console.error("PayPal error", err);
        alert("PayPal 出现错误，请重试");
      },
    }).render("#paypal-upgrade-btn");
  };
  tryRender();
}, [paymentConfig, user.plan, user.email, token, fetchUsage]);
```

- [ ] **Step 6: 替换 Header 中的升级按钮渲染**

找到原有的升级按钮区块（约第 431-435 行）：

```jsx
{user.plan === "free" ? (
  <a href={upgradeUrl} target="_blank" rel="noopener noreferrer" style={{...}}>Upgrade — $7/mo</a>
) : (
  <span style={{ fontSize: "12px", color: "#34d399", fontWeight: 600 }}>✦ Pro</span>
)}
```

替换为：

```jsx
{user.plan === "free" ? (
  paymentConfig?.payment_provider === "paypal" ? (
    <div id="paypal-upgrade-btn" style={{ minWidth: "150px" }} />
  ) : (
    <a
      href={`${paymentConfig?.checkout_url || ""}?checkout[custom][user_email]=${encodeURIComponent(user.email)}`}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        padding: "7px 16px", fontSize: "13px", fontWeight: 600,
        background: blue, color: "#fff", border: "none", borderRadius: "8px",
        textDecoration: "none", fontFamily: font,
      }}
    >Upgrade — $7/mo</a>
  )
) : (
  <span style={{ fontSize: "12px", color: "#34d399", fontWeight: 600 }}>✦ Pro</span>
)}
```

- [ ] **Step 7: 启动前端验证（LemonSqueezy 模式）**

```bash
cd frontend/listing-pilot && npm run dev
```

打开 http://localhost:5173，登录后确认 Header 中仍显示 "Upgrade — $7/mo" 链接（因为 `PAYMENT_PROVIDER=lemonsqueezy`）。

- [ ] **Step 8: Commit**

```bash
git add frontend/listing-pilot/src/App.jsx
git commit -m "feat: fetch /config and conditionally render PayPal button or LS link"
```

---

## Task 7: 整体冒烟测试

- [ ] **Step 1: 启动后端（LemonSqueezy 模式）**

```bash
cd backend && python main.py
```

```bash
curl http://localhost:8000/config
# Expected: {"payment_provider":"lemonsqueezy","checkout_url":"..."}
```

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.2.0"}
```

- [ ] **Step 2: 切换为 PayPal 模式**

在 `backend/.env` 中将 `PAYMENT_PROVIDER=lemonsqueezy` 改为 `PAYMENT_PROVIDER=paypal`，重启后端。

```bash
curl http://localhost:8000/config
# Expected: {"payment_provider":"paypal","paypal_client_id":"","paypal_plan_id":""}
```

- [ ] **Step 3: 前端验证 PayPal 按钮区域**

打开 http://localhost:5173，登录 free 账号，确认 Header 处出现 `<div id="paypal-upgrade-btn">`（PayPal SDK 未配置时按钮不会渲染，但容器存在）。

- [ ] **Step 4: 恢复 LemonSqueezy 模式（保持默认）**

```
PAYMENT_PROVIDER=lemonsqueezy
```

- [ ] **Step 5: Final commit**

```bash
git add backend/.env
git commit -m "chore: default PAYMENT_PROVIDER to lemonsqueezy"
```

---

## PayPal 上线前配置清单

完成代码后，在 PayPal Developer Dashboard 需要完成：

1. **创建 App** → 获取 `PAYPAL_CLIENT_ID` + `PAYPAL_CLIENT_SECRET`
2. **创建订阅 Plan**（Sandbox 先测试）→ 获取 `PAYPAL_PLAN_ID`
3. **配置 Webhook** → URL: `https://api.yourdomain.com/webhook/paypal`，选择 `BILLING.SUBSCRIPTION.*` 事件 → 获取 `PAYPAL_WEBHOOK_ID`
4. 上线时将 `PAYPAL_API_BASE` 从 `api-m.sandbox.paypal.com` 改为 `api-m.paypal.com`

---

## 变量切换速查

| 场景 | `.env` 设置 |
|------|------------|
| 使用 LemonSqueezy | `PAYMENT_PROVIDER=lemonsqueezy` |
| 使用 PayPal（sandbox） | `PAYMENT_PROVIDER=paypal` + 填入 PayPal sandbox 凭据 |
| 使用 PayPal（生产） | 同上 + 将 `PAYPAL_API_BASE` 改为生产地址 |
