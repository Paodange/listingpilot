# Creem 接入指南 — ListingPilot

本文档指导你在 [Creem](https://creem.io) 平台从 0 开始把支付跑通，覆盖**测试模式**和**真实模式**两套流程。

代码中所有支付相关逻辑都已替换为 Creem，读取的环境变量见 `backend/.env.example`：
`CREEM_API_KEY`、`CREEM_WEBHOOK_SECRET`、`CREEM_CHECKOUT_URL`、`CREEM_TEST_MODE`。

---

## 0. 工作原理（先看一眼，少踩坑）

```
[ 前端 Upgrade 按钮 ]
     │  打开 CREEM_CHECKOUT_URL?email=<用户邮箱>&request_id=<用户ID>
     ▼
[ Creem 托管收银台 ]  ← 用户填卡 / 用测试卡支付
     │
     │ 支付成功 / 订阅状态变更
     ▼
[ Creem 向 /webhook/creem 推送事件 ]
     │  Header: creem-signature  Body: JSON
     ▼
[ 后端验签 → 用 customer.email 查到用户 → 升降级 plan ]
```

关键点：

- **测试模式和真实模式是两套完全独立的环境**：API Key、Product、Payment Link、Webhook Secret 都是各自一套，互不通用。开发期间只用测试模式，上线时再切到真实模式。
- 后端通过 webhook payload 里的 `customer.email` 找到 ListingPilot 用户，所以**结账链接里必须把用户邮箱传进去**（前端已经这么做了：`?email=...`）。

---

## 1. 注册账号 & 完成 KYC

1. 打开 https://creem.io，点 **Get Started**，用邮箱注册。
2. 登录后，**Dashboard 默认在 Test Mode**（左上角或顶栏会有 Test/Live 切换器）。
3. 真实模式需要先做 KYC（个人或公司认证），测试模式不需要。先用测试模式跑通流程，KYC 可以稍后再做。

> **建议**：在 Creem 后台把浏览器停留在 **Test Mode**，下面所有"测试模式"步骤都在这个模式下完成。

---

## 2. 测试模式接入流程

### 2.1 创建 Test 产品

1. Dashboard 切到 **Test Mode**。
2. 进入 **Products** → **New Product**：
   - Name: `ListingPilot Pro (Test)`
   - Pricing model: **Recurring / Subscription**
   - Price: `5 USD`
   - Billing period: `Monthly`
3. 保存后，在产品详情页点 **Share** / **Payment Link**，复制 URL。
   - 测试链接形如：`https://www.creem.io/test/payment/prod_xxxxxxxxxx`
   - 注意路径里有 `/test/`——这是测试链接的标识。

### 2.2 拿到 Test API Key

1. Dashboard → **Developers** → **API Keys**。
2. 复制 Test 模式下的 Secret Key（前缀 `creem_test_`）。

### 2.3 配置 Test Webhook

需要一个公网可访问的 URL。本地开发推荐 [ngrok](https://ngrok.com/)：

```bash
# 启动后端
cd backend && uv run python main.py

# 另开一个终端把 8000 端口暴露出去
ngrok http 8000
# 复制输出里的 https://xxxx.ngrok-free.app
```

回到 Creem Dashboard：

1. **Developers** → **Webhooks** → **Add Endpoint**。
2. **Endpoint URL**: `https://xxxx.ngrok-free.app/webhook/creem`
3. **Events to send**：勾选下面这些（与后端 `/webhook/creem` 处理的事件一致）：
   - `checkout.completed`
   - `subscription.active`
   - `subscription.paid`
   - `subscription.canceled`
   - `subscription.expired`
4. 创建后，进入这个 Endpoint 的详情页，复制 **Signing Secret**。

### 2.4 写入 `.env`

```env
CREEM_API_KEY=creem_test_xxxxxxxxxxxxxxxxxxxx
CREEM_WEBHOOK_SECRET=<上一步复制的 signing secret>
CREEM_CHECKOUT_URL=https://www.creem.io/test/payment/prod_xxxxxxxxxx
CREEM_TEST_MODE=true
```

重启后端：`uv run python main.py`。

### 2.5 端到端测试

1. 前端 `npm run dev`，注册或登录任意账号。
2. 头部点 **Upgrade — $5/mo (Test)**（Test 标签由 `CREEM_TEST_MODE=true` 触发）。
3. 在 Creem 收银台用**测试卡**：
   - 卡号 `4242 4242 4242 4242`
   - 任意未来过期时间
   - 任意 3 位 CVC
   - 任意邮编
4. 支付完成后：
   - Creem Dashboard → Webhooks → 你的 endpoint，应能看到 `checkout.completed` / `subscription.active` 事件，状态 200。
   - 后端日志应无异常；数据库 `users` 表里对应用户 `plan` 变为 `pro`，`subscription_id` 写入。
   - 前端刷新（或下次打开），头部应显示 ✦ **Pro**。

> **取消订阅测试**：在 Creem Dashboard → Customers → 找到这个 customer → 取消其订阅，会触发 `subscription.canceled`，用户应被降回 free。

### 2.6 排查清单

- 看到 `403 Invalid webhook signature`：`CREEM_WEBHOOK_SECRET` 配错了，或者把 Live 的 secret 用到了 Test endpoint 上。
- 看到 `skipped: no customer email`：结账链接没带 `?email=`。检查前端 `App.jsx` 里那个 `<a href>`，`paymentConfig.checkout_url` 是否拿到。
- Webhook 在 Creem 端反复 retry：通常是后端 5xx 或 ngrok 隧道断了。Creem Dashboard 的 webhook 详情页可以手动 **Resend**。

---

## 3. 切换到真实模式（上线前）

测试模式跑通后，重复一遍流程到 Live Mode 即可。**所有资源都需要在 Live 模式下重新创建一份**。

1. **完成 KYC**：Dashboard → Settings → Verification，按指引提交身份/公司材料、绑定收款账户，等待审核通过。
2. Dashboard 切换到 **Live Mode**。
3. 重新做这几件事（和 §2.1–§2.3 一样，只是现在在 Live 模式下）：
   - 创建一个 Live 产品 `ListingPilot Pro`，$5/月订阅 → 复制 Live 收银链接（路径里**不含** `/test/`，形如 `https://www.creem.io/payment/prod_xxxxxxxxxx`）。
   - **Developers → API Keys** 复制 Live Secret Key（前缀 `creem_`，无 `test_`）。
   - **Developers → Webhooks** 新建一条指向你**生产域名**的 endpoint：`https://apicore.ntotech.top/webhook/creem`，订阅相同的 5 个事件，复制其 Live signing secret。
4. 在生产环境（不是本地 `.env`，是部署环境的环境变量）写入：
   ```env
   CREEM_API_KEY=creem_xxxxxxxxxxxxxxxxxxxx
   CREEM_WEBHOOK_SECRET=<live signing secret>
   CREEM_CHECKOUT_URL=https://www.creem.io/payment/prod_xxxxxxxxxx
   CREEM_TEST_MODE=false
   ```
5. 重启后端服务。
6. **小额真实测试**：本人或同事用一张真卡走一遍 $5 订阅，验证 webhook 进来、用户升级到 Pro，然后立刻在 Dashboard 把订阅取消并发起 refund，确认能回到 free。

> **绝对不要**把 Live 的 webhook secret 配到测试环境，反之亦然——签名一定会校验失败，且很容易混淆数据。

---

## 4. 测试模式 vs 真实模式 一图对照

| 项目 | 测试模式 | 真实模式 |
|---|---|---|
| Dashboard 切换 | 顶栏切到 **Test** | 顶栏切到 **Live**（需先 KYC） |
| API Key 前缀 | `creem_test_...` | `creem_...` |
| 收银链接路径 | `creem.io/test/payment/...` | `creem.io/payment/...` |
| Webhook 端点 | 指向 ngrok / 测试服务器 | 指向生产域名 |
| Signing Secret | Test 专用（与 Live 不同） | Live 专用 |
| 收款 | 不真实扣款，仅模拟 | 真实扣款 |
| 测试卡 | `4242 4242 4242 4242` | 真实信用卡 |
| `CREEM_TEST_MODE` | `true` | `false` |
| 何时使用 | 开发、QA、回归测试 | 仅生产环境 |

---

## 5. 后端代码对应关系（出问题时知道去哪儿改）

- **环境变量读取**：[backend/main.py](backend/main.py) 顶部 `CREEM_API_KEY` / `CREEM_WEBHOOK_SECRET` / `CREEM_CHECKOUT_URL` / `CREEM_TEST_MODE`。
- **签名校验**：[backend/main.py](backend/main.py) `_verify_creem_signature` —— HMAC-SHA256(secret, raw_body) 的 hex 摘要，与 `creem-signature` 头比对。
- **事件处理**：[backend/main.py](backend/main.py) `creem_webhook` —— 升级/降级用户的逻辑都在这里。
- **数据库订阅 ID**：[backend/database.py](backend/database.py) `users.subscription_id` 列，由 `update_user_plan(..., subscription_id=...)` 写入。
- **前端 /config**：[backend/main.py](backend/main.py) 末尾的 `get_config`，返回 `payment_provider`、`checkout_url`、`test_mode` 给前端。
- **前端按钮**：[frontend/listing-pilot/src/App.jsx](frontend/listing-pilot/src/App.jsx) 内 `paymentConfig?.checkout_url ? <a href=...>` 那段。
