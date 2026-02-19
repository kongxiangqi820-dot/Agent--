# Agent Framework (OpenAI Agents SDK)

这个仓库已改为 **OpenAI Agents SDK (Python)** 版本，支持：

- System Prompt (`agent.system_prompt`)
- Function Calling（本地工具）
- ReAct 风格循环（由 SDK 的 `Runner` 自动执行）
- 可选 MCP Server 接入（stdio / SSE / streamable_http）

## 1. Python 快速开始

1. 安装 Python 3.10+（建议 3.11/3.12）
2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

3. 设置环境变量

```powershell
$env:OPENAI_API_KEY="<your_key>"
# 可选
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
```

也可以用本地 `.env` 文件（推荐）：

1. 复制模板：`.env.example` -> `.env`
2. 把真实密钥只写进 `.env`（不要提交到 Git）
3. 直接运行 `run.cmd` / `run.ps1`，脚本会自动读取 `.env`

> 安全提醒：如果密钥曾经提交到仓库，请立刻去对应平台“轮换/作废”旧密钥。

4. 启动 CLI

```powershell
.\run.cmd
```

如果你的系统禁止执行 `.ps1`，`run.cmd` 会自动以 `ExecutionPolicy Bypass` 启动。

### FastAPI 服务（X-API-Key 鉴权）

1. 在 `.env` 中设置服务鉴权密钥：

```powershell
AGENT_API_KEY=your_service_api_key_here
```

2. 启动 API 服务：

```powershell
.\run-api.cmd
```

3. 调用聊天接口（必须带 `X-API-Key`）：

```powershell
curl -X POST "http://127.0.0.1:8000/v1/chat" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: your_service_api_key_here" `
  -H "X-Request-ID: req-demo-001" `
  -d "{\"message\":\"你好\",\"session_id\":\"s1\",\"user_id\":\"u1\",\"metadata\":{\"channel\":\"miniapp\"}}"
```

流式输出（SSE）：

```powershell
curl -N -X POST "http://127.0.0.1:8000/v1/chat/stream" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: your_service_api_key_here" `
  -H "X-Request-ID: req-stream-001" `
  -d "{\"message\":\"请流式回答：介绍一下你自己\",\"session_id\":\"s1\",\"user_id\":\"u1\"}"
```

SSE 事件说明：
- `start`: 本次流开始
- `delta`: 增量文本片段
- `done`: 最终完整响应（同 `/v1/chat` 统一结构）
- `error`: 失败响应（同统一错误结构）
- `end`: 流结束（`[DONE]`）

WebSocket 流式输出：

1. 建立连接（可用 query 传 `api_key`）：

```text
ws://127.0.0.1:8000/ws/chat?api_key=your_service_api_key_here
```

2. 发送请求（JSON）：

```json
{
  "request_id": "req-ws-001",
  "message": "请流式回答：介绍一下你自己",
  "session_id": "s1",
  "user_id": "u1",
  "metadata": {
    "channel": "miniapp"
  }
}
```

3. 接收事件：
- `start`
- `delta`
- `done`
- `error`
- `end`

4. 健康检查：

```powershell
curl "http://127.0.0.1:8000/healthz"
curl "http://127.0.0.1:8000/readyz"
```

说明：
- `/healthz`: 只检查服务进程是否存活
- `/readyz`: 检查密钥、会话存储可写性、MCP 可用性（用于故障切流）

`/v1/chat` 统一请求结构：

```json
{
  "message": "你好",
  "session_id": "s1",
  "user_id": "u1",
  "metadata": {
    "channel": "miniapp"
  }
}
```

`/v1/chat` 统一响应结构（成功）：

```json
{
  "code": 0,
  "message": "ok",
  "request_id": "req-demo-001",
  "timestamp": "2026-02-17T02:00:00Z",
  "data": {
    "answer": "你好，我在。",
    "latency_ms": 320,
    "session_id": "s1",
    "user_id": "u1",
    "tool_calls": [],
    "used_skills": []
  },
  "error": null
}
```

`/v1/chat` 统一响应结构（失败）：

```json
{
  "code": 1001,
  "message": "error",
  "request_id": "req-demo-001",
  "timestamp": "2026-02-17T02:00:00Z",
  "data": null,
  "error": {
    "type": "AUTH_ERROR",
    "http_status": 401,
    "biz_code": "AUTH_INVALID_API_KEY",
    "user_tip": "鉴权失败，请检查请求头 X-API-Key 是否正确。",
    "retryable": false,
    "action": "在请求头中携带正确的 X-API-Key。",
    "detail": "Unauthorized"
  }
}
```

常见 `code`（便于前端精细提示）：

- `1001`: 鉴权失败（X-API-Key 不正确）
- `1101`: `message` 为空
- `1102`: 请求参数格式错误（422）
- `2001`: 服务未就绪（建议先查 `/readyz`）
- `2101`: 模型密钥无效
- `2102`: 模型调用失败（可重试）
- `9000`: 未知内部错误

超时控制：

- 环境变量 `AGENT_RUN_TIMEOUT_SECONDS`（默认 `60` 秒）
- 超时会返回 `code=2103`（`MODEL_OR_MCP_TIMEOUT`）

日志格式（JSON）：

- 关键字段：`request_id`、`session_id`、`user_id`、`error_code`
- 事件：`request_received`、`request_succeeded`、`request_failed`

### Docker 部署（含 MCP 依赖锁定）

你可以把 FastAPI 直接容器化，不必先把所有 MCP 仓库手工下载到本地。

1. 可选：把需要锁版本的 GitHub 依赖写到 `requirements.mcp.txt`（推荐用 commit hash）

```txt
# 例子（按你的实际仓库替换）
git+https://github.com/your-org/your-mcp-server.git@0123456789abcdef0123456789abcdef01234567
```

2. 构建镜像

```powershell
docker build -t agentfw-api:skill .
```

> 注意：`requirements.mcp.txt` 修改后，需要重新 `docker build`（或 `docker compose up -d --build`）。

3. 运行容器（读取本地 `.env`，暴露 `8000`）

```powershell
docker run --rm -p 8000:8000 --env-file .env `
  -e AGENT_CONFIG=/app/agent.json `
  -v ${PWD}\.agent:/app/.agent `
  -v ${PWD}\agent.json:/app/agent.json:ro `
  -v ${PWD}\skills:/app/skills:ro `
  agentfw-api:skill
```

也可以用 `docker compose`：

```powershell
docker compose up -d --build
```

说明：

- `Dockerfile` 已包含 `node/npm/npx`，可支持常见 `stdio` MCP（例如 `npx @modelcontextprotocol/...`）。
- 远程 MCP（`streamable_http/sse`）不需要把服务端代码打进镜像，但需要容器可访问外网。
- 本地 `stdio` MCP 若依赖第三方包，建议在 `requirements.mcp.txt` 锁定版本，保证可复现和可回滚。

### Gemini 临时配置（OpenAI 兼容层）

已提供 `agent.gemini.json` 与一键脚本：

```powershell
$env:GEMINI_API_KEY="<your_gemini_key>"
.\run-gemini.cmd
```

等价环境变量为：

- `OPENAI_API_KEY=<your_gemini_key>`
- `OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`

`run-gemini` 也支持只设置 `GEMINI_API_KEY`（脚本会自动映射）。

### 密钥泄露自检

提供了一个本地脚本扫描常见密钥模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\security\check-secrets.ps1 -Root .
```

命中后脚本会返回非 0 状态码，适合放到你后续的 CI 里做拦截。

## 2. 配置说明（agent.json）

- `llm.provider`: 固定为 `openai_agents`
- `llm.openai_api`: `responses` 或 `chat_completions`
- `llm.base_url`: 可选，覆盖 `OPENAI_BASE_URL`
- `agent.system_prompt`: 系统提示词
- `agent.max_turns`: 最大循环轮次
- `tools.enabled`: 启用的本地工具
- `mcp.enabled`: 是否启用 MCP
- `mcp.servers`: MCP 服务列表

切换配置文件：

```powershell
.\run.ps1 -Config agent.gemini.json
```

内置本地工具：

- `echo`
- `time_now`
- `fs_list`
- `fs_read`

## 3. CLI 命令

- `/help` 查看帮助
- `/tools` 查看本地工具
- `/mcp` 查看 MCP 连接状态
- `/skills` 查看已加载技能
- `!tool {json}` 直接调用本地工具
- `/exit` 退出

## 4. Skills（可选）

本项目支持轻量 Skill 注入机制（与 MCP 可并行使用）：

- 配置位置：`agent.json -> skills`
- 默认目录：`skills/<skill-name>/SKILL.md`
- 触发方式：
  - 输入中包含 `$<skill-name>`
  - 输入中命中 `SKILL.md` frontmatter 的 `triggers`

`agent.json` 示例：

```json
{
  "skills": {
    "enabled": true,
    "dir": "skills",
    "max_active": 2,
    "allow_name_match": true
  }
}
```

示例技能：`skills/nearby-food-analysis/SKILL.md`

## 5. MCP 示例（stdio）

`agent.json` 里保留了一个示例：

```json
{
  "mcp": {
    "enabled": false,
    "servers": [
      {
        "name": "local-filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
      }
    ]
  }
}
```

把 `enabled` 改为 `true` 即可尝试连接。

默认 `agent.json` 已包含两个 MCP：

- `local-filesystem`
- `supabase`（通过 `mcp-remote` 连接 `https://mcp.supabase.com/mcp?read_only=true`）

说明：

- `agent.json` 默认不启用 MCP（避免未授权时影响启动）。
- 已提供 `agent.supabase.json`（启用 Supabase MCP + OpenAI）。
- 运行 Supabase（OpenAI）：`.\run-supabase.cmd`
- 启动 Supabase API（OpenAI）：`.\run-api-supabase.cmd`
- 已提供 `agent.supabase.gemini.json`（启用 Supabase MCP + Gemini，适合仅配置 `GEMINI_API_KEY` 的环境）。
- 运行 Supabase（Gemini）：`.\run-supabase-gemini.cmd`
- 启动 Supabase API（Gemini）：`.\run-api-supabase-gemini.cmd`
- 兼容保留了旧 `run-neon*.cmd` 脚本名，现已映射到 Supabase 配置。
- 首次 OAuth 需要浏览器授权；若 CLI 初始化超时，先单独运行一次：
  `cmd /c npx -y mcp-remote@latest https://mcp.supabase.com/mcp?read_only=true`

### Chrome DevTools MCP（已部署配置）

已新增配置文件：`agent.chrome-devtools.json`，内置：

- `chrome-devtools-mcp@latest`（通过 `cmd /c npx`，兼容 Windows 执行策略）
- `--headless --isolated --no-usage-statistics`

启动方式：

```powershell
.\run-devtools.cmd
```

或：

```powershell
.\run.ps1 -Config agent.chrome-devtools.json
```

进入 CLI 后可用 `/mcp` 查看连接状态。

## 6. JS 最小示例

仓库里有 `js-agent/`，使用 `@openai/agents`：

```powershell
cd .\js-agent
npm install
set OPENAI_API_KEY=<your_key>
npm run start
```

## 7. 目录

- `src/agentfw/cli.py`: CLI 入口（OpenAI Agents SDK）
- `src/agentfw/core/openai_agents_runtime.py`: SDK 运行时（模型、工具、MCP、Session）
- `src/agentfw/tools/`: 本地工具实现
- `agent.json`: 主配置
