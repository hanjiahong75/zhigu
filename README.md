# 知股 — AI 智能投研助手

基于 AI 的 A 股智能投研助手，支持自然语言对话、技术分析、持仓管理和微信接入。

## 已实现功能

- 💬 **AI 对话** — 自然语言交互，自动识别股票意图，调用实时行情 + 技术指标 + DeepSeek 生成专业分析
- 📊 **K 线图表** — 交互式 K 线图（MA/EMA/MACD/RSI/布林带）+ 分时图，支持日/周/月多周期切换
- 📋 **自选股管理** — 添加/删除自选股，实时行情刷新
- 💼 **持仓管理** — 手动录入股票/ETF/场外基金，自动计算盈亏、夏普比率、最大回撤
- 🧠 **长期记忆** — ChromaDB 向量存储，多次分析的股票自动累积知识
- 📱 **微信接入** — 通过 OpenClaw 连接微信，支持流式对话，与网页端共享同一 AI 管线

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React + Vite + Ant Design + ECharts |
| 后端 | FastAPI + SQLAlchemy + SQLite |
| AI | DeepSeek API（deepseek-chat）|
| 记忆 | ChromaDB + sentence-transformers |
| 微信 | OpenClaw Gateway + openclaw-weixin 插件 |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+
- Git

### 2. 安装后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 DeepSeek API Key
```

### 4. 启动

```bash
# 终端 1：后端
python backend/run.py

# 终端 2：前端
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173

### 5. 微信接入（可选）

```bash
npm install -g openclaw
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
# 配置 OpenClaw 使用本地方案 → 扫码登录微信
```

详见项目文档。

## 项目结构

```
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/       # API 路由
│   │   ├── models/    # 数据库模型
│   │   └── services/  # 业务逻辑（AI/行情/持仓/记忆）
│   └── .env.example   # 环境变量模板
├── frontend/          # React 前端
│   └── src/
│       ├── components/ # UI 组件
│       ├── api/        # API 客户端
│       └── types/      # TypeScript 类型
└── data/              # 数据库 & 上传文件
```
