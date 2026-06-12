# AGENTS.md — 知股 (ZhiGu) AI 投研助手

## 项目概览

前后端分离的 A 股智能投研助手。FastAPI 后端 + React 前端，DeepSeek 大模型驱动，
ChromaDB 向量记忆，已实现 AI Agent 自主决策、RAG 长期记忆、微信接入。

## 架构

```
frontend (localhost:5173)          backend (localhost:8000)
React + Vite + Antd + ECharts      FastAPI + SQLAlchemy + SQLite
       │                                    │
       ├── /api/chat ── (Agent) ────────────┤
       ├── /api/quote ──────────────────────┤
       ├── /api/kline ──────────────────────┤
       ├── /api/indicators ─────────────────┤
       ├── /api/watchlist ──────────────────┤
       ├── /api/portfolio ──────────────────┤
       └── /api/portfolio/risk ─────────────┤
                                            │
OpenClaw Gateway ──── /v1/chat/completions ─┤  (微信 SSE 流式)
                                            │
                                   DeepSeek API (云端)
                                   ChromaDB (本地向量库)
                                   东方财富/akshare (行情源)
```

## 目录结构

```
backend/
  app/
    main.py            FastAPI app 入口，注册 router + wechat_router
    config.py          所有配置（API key、超时、ChromaDB 路径）
    api/
      routes.py        两个 router：router(/api) + wechat_router(/v1)
    models/
      database.py      SQLite 引擎 + get_db() 依赖注入 + init_db() 迁移
      stock.py         7 个 ORM 模型（WatchlistItem → PortfolioItem）
    services/
      agent_tools.py   9 个 Function Calling 工具定义 + execute_tool()
      chat_service.py  chat_full / chat_full_stream / chat_agent / chat_agent_stream
      stock_data.py    akshare + 东方财富 API 行情抓取
      ai_analysis.py   DeepSeek 分析（单次调用，legacy）
      technical.py     纯 Python 技术指标（MA/EMA/MACD/RSI/布林带，无 talib）
      memory.py        ChromaDB 向量存储/检索
      retrieval.py     组合 ChromaDB + SQLite summary 构建上下文
      summarizer.py    滚动投资日志摘要（每 N 次分析触发一次 LLM 摘要）
      portfolio_service.py  持仓 OCR 识别 + 行情更新 + 风险计算
  run.py               uvicorn 启动入口 (reload=True)
  .env                 API key（不入 git）
  .env.example         环境变量模板
  requirements.txt

frontend/
  src/
    App.tsx            顶层布局（Header + MarketBar + ChatPanel）
    main.tsx           ReactDOM 入口
    api/client.ts      所有 fetch 封装（向后端 /api/* 发请求）
    types/index.ts     全部 TypeScript 类型定义
    components/
      ChatPanel.tsx    主对话面板（含侧边栏：对话线程 + 持仓）
      ChatStockCard.tsx 对话中的股票卡片（嵌入 K 线图）
      KlineChart.tsx   ECharts K 线图组件（多周期切换）
      Watchlist.tsx    自选股管理
      PortfolioPanel.tsx  持仓管理（手动录入/图片识别入口）
      StockSearch.tsx  股票搜索
      MarketBar.tsx    顶部市场指数条
      AnalysisPanel.tsx  历史分析面板
```

## 关键约定

### 后端

- **HTTP 客户端**: 全局使用 `curl_cffi.requests`（非 httpx/aiohttp），导入为 `from curl_cffi import requests`
- **DB 会话**: FastAPI 路由用 `Depends(get_db)`，Service 层手动用 `SessionLocal()` + try/finally
- **两个 Router**: `router` 挂 `/api` 前缀为前端服务；`wechat_router` 无前缀为 OpenClaw /v1 服务
- **国际化**: 所有用户提示、system prompt、错误消息用中文
- **API Key**: 统一从 `os.getenv("DEEPSEEK_API_KEY")` 获取，config.py 提供 `DEEPSEEK_API_KEY` 模块级变量
- **Agent 模式**: `/api/chat` 和 `/v1/chat/completions` 默认走 Agent（Function Calling），无需手动切换
- **流式传输**: SSE 格式 `data: {json}\n\n`，结束信号 `data: [DONE]\n\n`，元数据用 `:__meta__{json}` 传递

### 前端

- **K 线库**: 使用 `lightweight-charts`（非 ECharts），类型签名见 types/index.ts
- **组件库**: Ant Design 5.x + @ant-design/icons
- **状态管理**: 无全局状态库，全部用 React useState/useEffect
- **API 调用**: 全部封装在 `api/client.ts`，组件不直接写 fetch

### 通用

- **编码**: 所有文件 UTF-8，PowerShell 终端输出会显示乱码但实际编码正确
- **环境变量**: 后端用 python-dotenv 加载 `backend/.env`，模板在 `backend/.env.example`
- **根目录遗留文件**: `main.py`（独立版原型）、`_frontend_phase1.py`、`_gen_stock.py` 等为历史遗留，不要修改

## Agent 工具体系

Agent 通过 `agent_tools.py` 的 9 个工具实现自主决策：

| 工具名 | 功能 | 调用的 Service |
|--------|------|---------------|
| search_stock | 搜索股票 | stock_data.search_stocks() |
| get_stock_quote | 实时行情 | stock_data.get_realtime_quote() |
| get_kline_data | K 线数据 | stock_data.get_kline_data() |
| get_technical_indicators | 技术指标 | technical.calc_all_indicators() |
| get_market_overview | 市场指数 | stock_data.get_market_indices() |
| get_watchlist | 自选股 | DB: WatchlistItem |
| get_portfolio | 持仓 | portfolio_service.get_portfolio_with_prices() |
| get_portfolio_risk | 风险指标 | portfolio_service.calc_portfolio_risk() |
| retrieve_stock_memories | 历史记忆 | memory.retrieve_memories() |

Agent 最多 5 轮迭代，每轮超时 60 秒。

## 启动命令

```bash
# 后端
cd backend
python run.py

# 前端
cd frontend
npm run dev

# 微信（可选）
schtasks /Run /TN "OpenClaw Gateway"
```

## 常见陷阱

- **不要引入 httpx/aiohttp**: 项目统一用 `curl_cffi.requests`，混用会导致依赖膨胀
- **不要在 Service 层使用 Depends(get_db)**: 那是 FastAPI 路由专用，Service 用 `SessionLocal()` 手动管理
- **Chinese 编码问题**: 编辑 .py 文件确保 UTF-8 编码，终端乱码是 PowerShell 显示问题不是文件问题
- **wechat_router 无前缀**: 新增 OpenClaw 端点加在 wechat_router 上，不要加在 router 上（后者会变成 /api/v1/...）
- **不要删除根目录的 main.py 等遗留文件**: 它们是历史参考，不影响运行
- **Agent tools 返回 JSON 字符串**: execute_tool() 返回 json.dumps() 字符串，不是 dict；调用方会作为 tool message content 发给 LLM
- **lightweight-charts ≠ ECharts**: 前端 K 线图用的是 lightweight-charts 库，不是 ECharts
