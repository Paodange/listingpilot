# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指引。

## 项目概述

**ListingPilot** — 一个全栈 SaaS 应用，使用 DeepSeek AI API 生成电商平台产品列表（Amazon、Shopify、Etsy、eBay）。用户注册/登录后，提交产品信息，即可获得针对各平台优化的产品描述。付费套餐（通过 LemonSqueezy）可解锁更高的每日生成次数上限。

## 常用命令

### 后端（Python/FastAPI）

```bash
# 在项目根目录 — 先激活虚拟环境
source .venv/Scripts/activate   # Windows Git Bash
# 或
.venv\Scripts\activate           # Windows CMD/PowerShell

cd backend
pip install -r requirements.txt  # 安装依赖

python main.py                   # 在 8000 端口启动服务
```

### 前端（React/Vite）

```bash
cd frontend/listing-pilot
npm install
npm run dev      # 开发服务器，地址：http://localhost:5173
npm run build    # 生产环境构建
npm run lint     # ESLint 检查
npm run preview  # 预览生产构建
```

## 环境配置

将 `backend/.env.example` 复制为 `backend/.env`，并填写以下内容：

```
DEEPSEEK_API_KEY=        # DeepSeek API 密钥
JWT_SECRET=              # 72 位随机字符串
TOKEN_EXPIRE_HOURS=72
FREE_DAILY_LIMIT=3
PRO_DAILY_LIMIT=100
LEMONSQUEEZY_WEBHOOK_SECRET=
GOOGLE_CLIENT_ID=
ALLOWED_ORIGINS=http://localhost:5173
PORT=8000
```

## 架构说明

### 后端（`backend/`）

- **`main.py`** — FastAPI 应用，所有路由在此定义
- **`auth.py`** — JWT 创建/验证，SHA-256 密码哈希
- **`database.py`** — SQLite CRUD 操作；两张表：`users` 和 `usage_log`
- **`prompts.py`** — 各平台专属提示词构建器；通过 `PLATFORM_PROMPT_BUILDERS` 字典添加新平台

**路由分组：**
- `/auth/*` — 注册、登录、Google OAuth、`/auth/me`
- `/generate` — 主要列表生成接口（需要 Bearer token，检查每日限额）
- `/webhook/lemonsqueezy` — 将用户套餐从 `free` 升级为 `pro`
- `/health`

**数据库：** SQLite 文件位于 `backend/data/listingpilot.db`，首次运行时自动创建。代码注释中已标明计划迁移至 PostgreSQL。

**每日限额** 在 `/generate` 接口中通过 `usage_log` 表强制执行，限额值来自环境变量（`FREE_DAILY_LIMIT`、`PRO_DAILY_LIMIT`）。

### 前端（`frontend/listing-pilot/src/`）

- **`App.jsx`** — 单文件单体（约 596 行），包含所有 UI：`AuthScreen`、`MainApp`（生成表单）和 `ResultPanel`
- 无路由库 — 页面通过 React state 切换
- JWT 存储在 `localStorage`，以 `Authorization: Bearer` 请求头传递
- API 基础地址硬编码：开发环境为 `http://localhost:8000`，生产环境为 `https://apicore.ntotech.top`

### 数据流

1. 用户认证 → JWT 存入 localStorage
2. 用户提交产品表单（名称、特性、目标受众、平台、语气）
3. 前端携带 Bearer token POST 请求 `/generate`
4. 后端检查每日使用限额，调用 DeepSeek API 并使用平台专属提示词
5. 返回各平台产品列表的 JSON；使用次数递增

## 关键设计决策

- 所有前端逻辑集中在 `App.jsx` — 有意保持 MVP 简洁性，不引入状态管理库
- 全部使用内联 CSS（不使用 Tailwind 或其他 CSS 框架）
- SQLite 为临时方案；架构设计支持切换至 PostgreSQL
- 平台支持可扩展 — 在 `prompts.py` 的 `PLATFORM_PROMPT_BUILDERS` 中添加新平台，无需修改路由
