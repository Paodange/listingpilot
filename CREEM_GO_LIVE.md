# Creem 真实模式上线 SOP — ListingPilot

测试模式已经跑通的前提下，按本文从上到下做就能切到 Live。每一步都给了**做什么**和**怎么验证已经做对**。

> **重要原则**：测试模式和真实模式是完全独立的两套（产品、API Key、Webhook、Signing Secret 各一份），它们之间任何配置错配都会签名失败或事件丢失。复制 - 粘贴时仔细确认是 Live 那一套。

---

## 0. 前置检查（30 秒）

跑通这两条命令，确认现有测试模式是工作的：

```bash
curl -s https://apicore.ntotech.top/config
# 应返回 {"payment_provider":"creem","checkout_url":"https://www.creem.io/test/payment/...","test_mode":true}
```

```bash
curl -s https://apicore.ntotech.top/health
# {"status":"ok","version":"0.3.0"}
```

外加：

- [ ] Creem Dashboard 的 **KYC / Verification 已审核通过**（Settings → Verification 显示 Approved）。没通过就先去做，可能要 1–3 个工作日。
- [ ] 已经绑定了**收款账户**（Settings → Payouts），不然钱过不来。

KYC 没过之前**根本切不到 Live Mode**，先停在这里。

---

## 1. Creem Dashboard 切到 Live Mode 并配置

> 整个 §1 都在 Creem Dashboard **Live Mode** 下操作（顶栏 Test/Live 切换器切到 Live）。

### 1.1 创建 Live 产品

Products → **New Product**：

| 字段 | 值 |
|---|---|
| Name | `ListingPilot Pro` |
| Pricing model | Recurring / Subscription |
| Price | `5 USD` |
| Billing period | `Monthly` |
| Description | （从 [CREEM_SETUP.md] 之前的产品描述复制 A 段） |
| Logo | 上传 `icon.png`（项目根目录） |

保存后进产品详情 → **Share** → 复制 Payment Link，形如：

```
https://www.creem.io/payment/prod_xxxxxxxxxx
```

**核对点**：URL 路径**不含** `/test/`，包含 `/payment/`。如果看到 `/test/`，说明你还在 Test Mode 没切过来。

### 1.2 拿 Live API Key

Developers → API Keys → 复制 Live 模式下的 Secret Key。

**核对点**：前缀是 `creem_`，**不是** `creem_test_`。

### 1.3 配置 Live Webhook

Developers → Webhooks → **Add Endpoint**：

| 字段 | 值 |
|---|---|
| URL | `https://apicore.ntotech.top/webhook/creem` |
| Events | 勾选这五个：`checkout.completed`、`subscription.active`、`subscription.paid`、`subscription.canceled`、`subscription.expired` |

创建完点进 Endpoint 详情 → 复制 **Signing Secret**。

**核对点**：这个 secret 跟你测试模式那个**完全不同**。混用会一直 403。

---

## 2. 切换生产后端环境变量

打开生产环境的 `.env`（你刚在 IDE 里编辑的就是 [backend/.env](backend/.env) 那份，假设它就是部署机上用的；不是的话改部署机上那份）。

把这四个变量从 Test 值替换为 Live 值：

```env
CREEM_API_KEY=creem_xxxxxxxxxxxxxxxxxxxx              # ← §1.2 拿到的 Live Key
CREEM_WEBHOOK_SECRET=<live_signing_secret>            # ← §1.3 拿到的 Live signing secret
CREEM_CHECKOUT_URL=https://www.creem.io/payment/prod_xxxxxxxxxx  # ← §1.1 链接（无 /test/）
CREEM_TEST_MODE=false                                 # ← 关键：必须改成 false
```

**ALLOWED_ORIGINS** 也确认一下含生产前端域名（这步通常之前就配好了）：
```env
ALLOWED_ORIGINS=https://cc.ntotech.top
```

保存。

---

## 3. 重启后端 + 验证

按你后端的实际部署方式重启进程：

```bash
# 如果是 systemd
sudo systemctl restart listingpilot

# 如果是 pm2
pm2 restart listingpilot

# 如果是 docker / docker compose
docker compose restart backend

# 如果是 screen/tmux 里手跑的，kill 掉重起
```

**验证 1：/config 返回 Live URL**

```bash
curl -s https://apicore.ntotech.top/config
```

期望输出（注意 `test_mode` 是 `false`，URL 无 `/test/`）：

```json
{"payment_provider":"creem","checkout_url":"https://www.creem.io/payment/prod_xxxxxxxxxx","test_mode":false}
```

**验证 2：前端按钮文案不再带 (Test)**

打开 https://cc.ntotech.top，登录一个 free 账号。头部按钮应是 `Upgrade — $5/mo`（**没有** `(Test)` 后缀）。如果还带 (Test)，浏览器可能缓存了旧 `/config`，硬刷新（Ctrl+Shift+R）一次。

---

## 4. 真卡小额验证（必做）

**用一个干净的测试账号**（不要用 liudp88@gmail.com 这种重要账号，避免污染数据）：

1. 在 https://cc.ntotech.top 注册新账号 `golive-test+1@yourmail.com` 之类。
2. 点 Upgrade，跳到 Creem 收银台，**用真信用卡**支付 $5。
3. 立即检查：

   **a.** Creem Dashboard（Live Mode） → Webhooks → 你那个 endpoint → 有 `checkout.completed` 和 `subscription.active` 事件，状态 200。
   
   **b.** 后端日志没有 403 / 500。
   
   **c.** 数据库 `users` 表里这个邮箱 `plan = pro`、`subscription_id` 已写入：
   ```bash
   sqlite3 backend/data/listingpilot.db "SELECT email, plan, subscription_id FROM users WHERE email='golive-test+1@yourmail.com';"
   ```
   
   **d.** 前端刷新，头部显示 `✦ Pro`。

4. **立即在 Creem Dashboard 取消并退款**（Customers → 找这个 customer → Cancel Subscription，再 Refund 那笔 $5）：
   
   **a.** Webhook 应收到 `subscription.canceled`，后端日志应无报错。
   
   **b.** 数据库该用户 `plan` 回到 `free`。
   
   **c.** 信用卡退款几小时到几天会到账。

如果 a~d 全过，**真实模式就上线完成了**。

---

## 5. 上线后续维护清单

- [ ] **保留** Test Mode 那条 webhook endpoint（可以让它指向 ngrok 或者 dev 后端），将来本地开发还要用。但如果它指向 `apicore.ntotech.top` 这个生产域名，**马上把它停用或删掉**——否则 Test 事件会污染生产数据库。
- [ ] **环境变量永远不要进 git**。检查一下 `backend/.env` 在 `.gitignore` 里：
  ```bash
  grep -c "^backend/.env$\|^.env$" .gitignore
  ```
  没忽略的话立即加上。
- [ ] **监控 webhook 失败**：Creem Dashboard → Webhooks → endpoint → Events，定期看一眼有没有红色失败。失败原因通常是后端 5xx 或签名错。
- [ ] **首单监控**：第一个真实付费用户进来时，盯一下 webhook 200 + 数据库 plan 同步。
- [ ] **退订流程**：用户要退订时，目前没有自助入口，需要他们邮件你 → 你在 Creem Dashboard 手动取消。后续可以加个 `/billing/portal` 路由调 Creem Customer Portal API。

---

## 6. 出事时回滚

如果上线后发现支付有问题，**先恢复服务、再排查**：

1. 把 `.env` 里 `CREEM_TEST_MODE=true`，`CREEM_CHECKOUT_URL` 换回 Test URL，重启后端。前端 Upgrade 按钮会马上指回测试链接，**不会再产生新的真实扣款**。
2. 已经扣过钱的真实订单：在 Creem Dashboard 手动 Refund，对用户也手动把 `plan` 改回 `free`：
   ```bash
   sqlite3 backend/data/listingpilot.db "UPDATE users SET plan='free' WHERE email='受影响用户';"
   ```
3. 排查完再切回 Live。

---

## 附：本次切换涉及的文件 / 不涉及的文件

**改动的**（环境变量层面）：
- 部署机的 `backend/.env`（4 个 `CREEM_*` 变量）

**不需要改代码**：
- [backend/main.py](backend/main.py) — 同一份代码同时支持 Test/Live，看 `CREEM_TEST_MODE` 切。
- [frontend/listing-pilot/src/App.jsx](frontend/listing-pilot/src/App.jsx) — `(Test)` 后缀根据 `/config` 返回的 `test_mode` 自动切，不用重新部署前端。
- 数据库 schema —— 测试模式产生的真实用户数据（如果有）会保留，无需迁移。
