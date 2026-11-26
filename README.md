# 聚光 FocusIn · 消息智能体聚合平台

> 聚光：聚合消息，聚焦要事。**不是让你看更多消息，而是让你少看消息。**

本地优先的消息聚合 + AI 分诊 + Agent 执行平台：把微信、QQ、飞书、抖音群聊、钉钉和邮箱的消息汇于一处，智能体以这些消息为工作上下文，在平台内直接完成摘要、排程、检索与起草——全程不跳转任何页面。

本仓库为 **3 天可演示 Demo**（对应需求文档 v1.5 的 P0 裁剪范围）：

- 消息汇总：8 会话 × 200+ 条模拟工作消息数据集（含待办/日程/通知/重要/闲聊混合）
- 五分组分诊 + 会话摘要（规则兜底，配 LLM Key 后升级）
- 防幻觉日程提取：展示原文依据 → 用户确认 → 落库提醒
- Agent 对话：多模型 OpenAI 兼容（SSE 流式）+ 工具注册表 + HITL 审批门 + 全量审计
- 演示闭环零依赖：无 API Key / 断网时走本地规则模式，P0 闭环照常演示

## 快速开始

```bash
# 1. 后端（Python 3.10+）
cd backend
uv venv .venv && uv pip install -r requirements.txt   # 或 pip
.venv/Scripts/python -m uvicorn app:app --host 127.0.0.1 --port 8765

# 2. 前端（Node 18+）
cd web
npm install && npm run dev
```

或 Windows 下直接双击 `start.bat`。浏览器打开 http://localhost:5180。

## 演示路径（P0 闭环）

1. **纵览页**：Hero 横幅看今日一句话 → 渠道卡片 →「继续查看」消息卡片流 → 今日简报表
2. **消息流页**：点「模拟新消息入站」→ 涟漪动画 + 分诊徽章弹跳；若含时间则生成待确认日程
3. **日历页**：待确认日程卡展示原文依据 → 「确认入库」
4. **对话页**：输入「领导上周关于报销说了什么」→ 检索工具带出处回答；「提醒我周五下午 3 点开会」→ 触发 HITL 审批弹窗
5. **设置页**：填入任意 OpenAI 兼容 API（DeepSeek/通义/Kimi/智谱等）后，对话升级为真实 LLM + Function Calling

## 架构

```
backend/                Python FastAPI · SQLite · SSE
  app.py                本地服务进程（HTTP API + WebSocket 预留）
  dataset.py            模拟工作消息数据集（兜底演示）
  triage.py             五分组分诊 + 自然语言时间提取（防幻觉：无明确日期不创建）
  llm.py                LLM 网关（OpenAI 兼容，流式；无 Key 不可用）
  agent.py              工具注册表（schema+风险分级）→ Sentinel 审批门 → 执行 → 审计
web/                    Vue 3 + Vite（纵览/消息流/日历/对话/设置）
```

设计参考：EvoFlow（Channel 基类/调度/任务可观测）、Happy Friday Lite（工具注册表/HITL/提示词锁定日程）、nanoMuse（Sentinel 风险分级/形象情绪/克制调色板），详见需求文档附录。

## 合规边界

- 飞书/钉钉/邮箱：官方 API，用户自行授权
- 微信/QQ/抖音：实验性本地只读插件（本 Demo 以模拟数据演示效果），可一键停用
- 外发动作（邮件/群消息）永远只起草，发送由用户显式完成
