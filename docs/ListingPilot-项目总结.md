# ListingPilot — 出海AI小工具项目总结

## 一、项目定位

**产品名称**：ListingPilot（暂定）

**一句话描述**：AI电商产品描述生成器 — 用户输入一次产品信息，同时生成 Amazon / Shopify / Etsy / eBay 四个平台的优化listing文案。

**目标用户**：海外跨境电商卖家（Amazon/Shopify/Etsy/eBay卖家）

**核心差异化**：一次输入，多平台输出。每个平台输出格式不同（Amazon要5条bullet points、Shopify带SEO meta、Etsy有手工艺风格排版和tags、eBay有item specifics）。

**项目核心目标**：不是追求产品完美，而是通过这个最小产品**跑通出海全链路**——收款、推广、VPS部署、域名配置、SEO、用户反馈。这些经验可复用到后续任何出海产品。

---

## 二、商业模式

| 项目 | 方案 |
|------|------|
| 定价 | 免费用户每天3次，Pro $7/月不限次（100次/天） |
| 收款 | LemonSqueezy（MoR模式，处理全球税务，个人可注册，无需海外公司） |
| 付费流程 | 用户点升级 → 跳转LemonSqueezy付款 → webhook回调后端自动升级plan |

---

## 三、技术架构

```
海外用户 → Vercel(前端) → Cloudflare(反向代理/HTTPS) → 国内服务器(FastAPI后端) → DeepSeek API
```

### 技术栈选择

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React (Vite) | 部署到 Vercel（免费） |
| 后端 | FastAPI + SQLite | 部署到国内现有服务器 |
| LLM | DeepSeek API | 国内可直接调用，成本极低 |
| 域名/CDN | Cloudflare | 免费CDN + HTTPS + 反向代理隐藏源站IP |
| 收款 | LemonSqueezy | webhook回调自动升级用户 |
| 登录 | 邮箱密码 + Google OAuth | JWT token认证 |

### 为什么用国内服务器

- 不需要额外买VPS，复用现有机器
- DeepSeek API是国内服务，调用无延迟
- 通过Cloudflare反向代理对外提供HTTPS服务
- 启动成本降到几乎为零
- 等有付费用户后再考虑迁移海外VPS

---

## 四、成本估算

| 项目 | 费用 |
|------|------|
| 域名 | ~$10/年 |
| Vercel前端托管 | 免费 |
| 国内服务器 | 已有，$0 |
| DeepSeek API | 按量付费，前期 <$1/月 |
| LemonSqueezy | 5% + $0.50 每笔交易 |
| **总启动成本** | **~$10** |

---

## 五、后端项目结构

```
listing-pilot-backend/
├── main.py           # FastAPI主程序（路由、API调用、webhook）
├── auth.py           # JWT token + 密码哈希（SHA-256加盐）
├── database.py       # SQLite用户存储 + 用量追踪
├── prompts.py        # 四个平台的prompt模板
├── requirements.txt  # 依赖清单
├── .env.example      # 环境变量模板
└── data/             # SQLite数据库文件（自动创建）
```

### API Endpoints

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/auth/register` | 邮箱密码注册 | 无 |
| POST | `/auth/login` | 邮箱密码登录 | 无 |
| POST | `/auth/google` | Google OAuth登录/注册 | 无 |
| GET | `/auth/me` | 获取用户信息+今日用量 | Bearer token |
| POST | `/generate` | 生成listing（支持多平台并发） | Bearer token |
| POST | `/webhook/lemonsqueezy` | 接收支付回调，自动升降级 | 签名验证 |
| GET | `/health` | 健康检查 | 无 |

### 关键设计

- **并发生成**：选多个平台时，用 `asyncio.gather` 并发调用DeepSeek，而非串行
- **用量控制**：按用户ID + 日期追踪，free用户3次/天，pro用户100次/天
- **LemonSqueezy集成**：前端生成checkout链接时拼接用户email作为custom_data，webhook回调时通过email匹配用户并升级plan
- **Google OAuth**：后端用Google tokeninfo API验证id_token，自动创建或查找用户

---

## 六、前端设计

### 页面结构

1. **登录/注册页**：邮箱密码表单 + Google Sign-In按钮 + Log In / Sign Up切换
2. **主界面**：
   - 顶栏：logo、剩余次数、升级按钮、用户邮箱、登出
   - 输入区：产品名称、特点、目标受众、平台多选、语气选择
   - 结果区：按平台分tab展示，每个区块有Copy按钮，右上角Copy All

### 每个平台输出内容

| 平台 | 输出内容 |
|------|----------|
| Amazon | Title + 5条Bullet Points（带emoji）+ Description |
| Shopify | Title + Description（带✓清单）+ SEO Meta Title & Description |
| Etsy | Title（带•分隔符）+ Description（带━━━装饰分隔）+ 7个Tags |
| eBay | Title（80字符内）+ Description（带▬▬▬分隔）+ Item Specifics键值对 |

---

## 七、部署步骤

### 后端部署（国内服务器）

```bash
# 1. 上传项目到服务器
# 2. 创建虚拟环境
python -m venv venv && source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入：
#   DEEPSEEK_API_KEY（从 platform.deepseek.com 获取）
#   JWT_SECRET（随机字符串）
#   GOOGLE_CLIENT_ID（从 Google Cloud Console 获取）
#   ALLOWED_ORIGINS（你的Vercel前端域名）

# 5. 启动
python main.py

# 6. 用systemd设置开机自启（见README）
```

### Cloudflare配置

1. 添加 A/AAAA 记录：`api.yourdomain.com` → 服务器IP
2. 开启 Cloudflare 代理（橙色云朵）
3. SSL/TLS → Full (strict)

### 前端部署（Vercel）

```bash
# 1. 创建Vite项目
npm create vite@latest listing-pilot -- --template react
cd listing-pilot

# 2. 把 listing-pilot-frontend.jsx 内容替换到 src/App.jsx
# 3. 修改文件顶部的 API_BASE、LEMONSQUEEZY_CHECKOUT、GOOGLE_CLIENT_ID

# 4. 本地测试
npm run dev

# 5. 部署到Vercel
npm i -g vercel
vercel
```

### Google OAuth配置

1. 去 console.cloud.google.com
2. APIs & Services → Credentials → Create Credentials → OAuth Client ID
3. Application type: Web application
4. Authorized JavaScript origins: 添加前端域名
5. 拿到 Client ID，填入后端 `.env` 和前端代码

### LemonSqueezy配置

1. 注册 lemonsqueezy.com（个人账号即可）
2. 创建Store → 创建Product（$7/月订阅）
3. Settings → Webhooks → 添加 `https://api.yourdomain.com/webhook/lemonsqueezy`
4. 选择事件：subscription_created, subscription_updated, subscription_cancelled, subscription_expired
5. 复制 signing secret 到 `.env` 的 `LEMONSQUEEZY_WEBHOOK_SECRET`
6. 前端的 `LEMONSQUEEZY_CHECKOUT` 填入你的checkout链接

---

## 八、推广计划（第3-4周）

### 冷启动渠道

| 渠道 | 做法 |
|------|------|
| Reddit | r/AmazonSeller, r/Etsy, r/ecommerce, r/SideProject 发帖分享工具 |
| Product Hunt | 做一次正式Launch（周二至周四上午发布效果最好） |
| Dev.to / Medium | 写 "I built an AI listing generator in a weekend" 文章 |
| Twitter/X | 搜索 "amazon listing" 相关话题互动 |
| SEO | 写2-3篇英文博客瞄准长尾关键词（如 "AI amazon listing generator free"） |

---

## 九、域名建议

### 注册平台

- **首选 Cloudflare Registrar**：成本价卖域名，后续DNS/CDN零配置
- **备选 Namecheap**：价格便宜，首年常有优惠
- **避开 GoDaddy**：续费贵，推销多

### 命名思路

建议垂直命名（自带SEO优势），示例方向：
- 动词+名词型：listingcraft.ai、quicklisting.com、listingpilot.com
- 功能直述型：ailistingwriter.com、productcopyai.com
- 品牌+垂直型：copylisto.com、listora.ai

优先 .com，.ai域名偏贵（$20-80/年）。不要纠结太久，20分钟选定即可。

---

## 十、后续迭代方向

等MVP跑通链路、拿到用户反馈后，可能的迭代：

- 支持上传产品图片，AI自动提取产品特征
- 批量CSV导入，一次生成多个产品的listing
- SEO关键词建议/竞品分析
- 支持更多平台（Walmart、Wish等）
- 生成历史记录保存
- 切换LLM（从DeepSeek切到Claude/GPT测试效果差异）

---

## 十一、关键提醒

> **不要在第一个产品上追求完美。它的使命是帮你交学费、跑通流程。哪怕最终只赚了$50，但你把整条链路走通了，第二个产品的启动速度会快10倍。**

待全链路跑通后，可以快速复制到其他AI小工具方向（如AI Changelog生成器、AI邮件改写器），收款/部署/推广基础设施直接复用。
