# PayPal Payment Provider Design

## Summary

在保留 LemonSqueezy 方案的前提下，新增 PayPal 订阅支付方案。通过环境变量 `PAYMENT_PROVIDER` 控制激活哪套，前端根据后端 `/config` 接口动态渲染对应按钮。

## Architecture

- `PAYMENT_PROVIDER=lemonsqueezy|paypal` 控制激活方案
- 后端新增 `/config`、`/paypal/capture`、`/webhook/paypal` 接口；保留 `/webhook/lemonsqueezy`
- 数据库 `users` 表新增 `pp_subscription_id` 字段；保留 `ls_*` 字段
- 前端启动时请求 `/config`，按 provider 渲染不同升级按钮

## Payment Flow（PayPal 路径）

1. 前端加载 PayPal JS SDK（含 `vault=true&intent=subscription`）
2. 用户点击 PayPal 订阅按钮 → 弹窗授权
3. `onApprove(subscriptionID)` → POST `/paypal/capture`
4. 后端调 PayPal REST API 验证订阅状态 → 升级套餐
5. 前端刷新 `/auth/me` → 显示 Pro

## PayPal Webhook（订阅取消/过期）

- PayPal 后台推送 `BILLING.SUBSCRIPTION.CANCELLED` / `BILLING.SUBSCRIPTION.EXPIRED`
- 后端 `/webhook/paypal` 调 PayPal verify API 验证签名
- 验证通过 → 降级套餐为 free

## Env Vars

```
PAYMENT_PROVIDER=paypal
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_PLAN_ID=
PAYPAL_WEBHOOK_ID=
```

## Database

`users` 表新增：
- `pp_subscription_id TEXT DEFAULT ''`

保留原有：
- `ls_customer_id`
- `ls_subscription_id`
