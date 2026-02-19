from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

from agents import Runner
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from agentfw.core.config import load_config
from agentfw.core.openai_agents_runtime import (
    build_agent,
    build_mcp_manager,
    build_mcp_servers,
    build_session,
    configure_openai,
)
from agentfw.core.skills import compose_prompt_with_skills, load_skill_store
from agentfw.tools.registry import ToolRegistry, build_default_tools


_LOG = logging.getLogger("agentfw.api")
if not _LOG.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _LOG.addHandler(_h)
_LOG.setLevel(logging.INFO)
_LOG.propagate = False


def _log_json(level: str, **payload: Any) -> None:
    out = {"timestamp": _now_utc_iso(), **payload}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if level == "error":
        _LOG.error(text)
    elif level == "warning":
        _LOG.warning(text)
    else:
        _LOG.info(text)


def _format_output(value: Any) -> str:
    if value is None:
        return "(empty response)"
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _build_registry(cfg: dict[str, Any]) -> ToolRegistry:
    reg = ToolRegistry()
    tools_cfg = cfg.get("tools", {}) or {}
    enabled = tools_cfg.get("enabled") or []
    fs_root = tools_cfg.get("fs_root") or "."

    for t in build_default_tools(fs_root=fs_root):
        reg.register(t)

    if enabled:
        reg.enable_only(set(enabled))

    return reg


@dataclass
class AppRuntime:
    cfg: dict[str, Any]
    config_path: Path
    registry: ToolRegistry
    session: Any
    max_turns: int
    llm_cfg: dict[str, Any]
    agent_cfg: dict[str, Any]
    skill_store: Any
    active_servers: list[Any]
    mcp_manager: Any
    agent_cache: dict[tuple[str, ...], Any] = field(default_factory=dict)

    def agent_for_input(self, user_input: str):
        active_skills = self.skill_store.match(user_input) if self.skill_store is not None else []
        key = tuple(skill.name for skill in active_skills)
        if key in self.agent_cache:
            return self.agent_cache[key], active_skills

        scoped_agent_cfg = dict(self.agent_cfg)
        base_prompt = str(self.agent_cfg.get("system_prompt") or "")
        scoped_agent_cfg["system_prompt"] = compose_prompt_with_skills(base_prompt, active_skills)

        agent = build_agent(
            agent_cfg=scoped_agent_cfg,
            llm_cfg=self.llm_cfg,
            registry=self.registry,
            mcp_servers=self.active_servers,
        )
        self.agent_cache[key] = agent
        return agent, active_skills


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User input text")
    session_id: str | None = Field(default=None, description="Client-side session id")
    user_id: str | None = Field(default=None, description="Client-side user id")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional client metadata")


class ChatData(BaseModel):
    answer: str
    latency_ms: int
    session_id: str | None
    user_id: str | None
    tool_calls: list[str]
    used_skills: list[str]


class ApiResponse(BaseModel):
    code: int
    message: str
    request_id: str
    timestamp: str
    data: dict[str, Any] | ChatData | None = None
    error: dict[str, Any] | None = None


def _validate_api_key(x_api_key: str | None) -> None:
    expected = os.environ.get("AGENT_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="AGENT_API_KEY is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    _validate_api_key(x_api_key)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _api_ok(*, request_id: str, data: dict[str, Any] | ChatData, message: str = "ok") -> dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "request_id": request_id,
        "timestamp": _now_utc_iso(),
        "data": data.model_dump() if isinstance(data, BaseModel) else data,
        "error": None,
    }


def _api_err(
    *,
    request_id: str,
    code: int,
    message: str,
    error_type: str,
    http_status: int,
    biz_code: str,
    user_tip: str,
    retryable: bool,
    action: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
        "timestamp": _now_utc_iso(),
        "data": None,
        "error": {
            "type": error_type,
            "http_status": http_status,
            "biz_code": biz_code,
            "user_tip": user_tip,
            "retryable": retryable,
        },
    }
    if action:
        payload["error"]["action"] = action
    if detail:
        payload["error"]["detail"] = detail
    return payload


def _classify_error(http_status: int, detail: str) -> dict[str, Any]:
    text = (detail or "").lower()

    if http_status == 401 and "unauthorized" in text:
        return {
            "code": 1001,
            "error_type": "AUTH_ERROR",
            "biz_code": "AUTH_INVALID_API_KEY",
            "user_tip": "鉴权失败，请检查请求头 X-API-Key 是否正确。",
            "retryable": False,
            "action": "在请求头中携带正确的 X-API-Key。",
        }
    if "agent_api_key is not configured" in text:
        return {
            "code": 1002,
            "error_type": "CONFIG_ERROR",
            "biz_code": "AUTH_SERVICE_KEY_MISSING",
            "user_tip": "服务端未配置 AGENT_API_KEY。",
            "retryable": False,
            "action": "在 .env 中设置 AGENT_API_KEY 并重启服务。",
        }
    if http_status == 400 and "message must not be empty" in text:
        return {
            "code": 1101,
            "error_type": "VALIDATION_ERROR",
            "biz_code": "REQ_EMPTY_MESSAGE",
            "user_tip": "消息内容不能为空。",
            "retryable": False,
            "action": "请传入非空 message。",
        }
    if http_status == 422:
        return {
            "code": 1102,
            "error_type": "VALIDATION_ERROR",
            "biz_code": "REQ_INVALID_SCHEMA",
            "user_tip": "请求参数格式不正确。",
            "retryable": False,
            "action": "检查 message/session_id/user_id 字段类型和必填项。",
        }
    if http_status == 503 and "service is not ready" in text:
        return {
            "code": 2001,
            "error_type": "SERVICE_NOT_READY",
            "biz_code": "SERVICE_NOT_READY",
            "user_tip": "服务尚未就绪，请稍后重试。",
            "retryable": True,
            "action": "先调用 /readyz 确认就绪状态。",
        }
    if "incorrect api key provided" in text or "invalid_api_key" in text:
        return {
            "code": 2101,
            "error_type": "MODEL_AUTH_ERROR",
            "biz_code": "MODEL_INVALID_API_KEY",
            "user_tip": "模型密钥无效，请检查 OPENAI_API_KEY 或 GEMINI_API_KEY。",
            "retryable": False,
            "action": "更新有效模型密钥并重启服务。",
        }
    if "chat_failed" in text:
        return {
            "code": 2102,
            "error_type": "MODEL_CALL_ERROR",
            "biz_code": "MODEL_CALL_FAILED",
            "user_tip": "模型调用失败，请稍后重试。",
            "retryable": True,
            "action": "查看日志中的 request_id 定位问题。",
        }
    if http_status == 504 or "chat_timeout" in text:
        return {
            "code": 2103,
            "error_type": "TIMEOUT_ERROR",
            "biz_code": "MODEL_OR_MCP_TIMEOUT",
            "user_tip": "请求超时，请稍后重试。",
            "retryable": True,
            "action": "可重试，或提高 AGENT_RUN_TIMEOUT_SECONDS。",
        }
    return {
        "code": 9000,
        "error_type": "INTERNAL_ERROR",
        "biz_code": "INTERNAL_UNKNOWN",
        "user_tip": "服务内部错误，请稍后重试或联系管理员。",
        "retryable": True,
        "action": "记录 request_id 后排查后端日志。",
    }


def _to_float(value: str | None, default: float) -> float:
    try:
        v = float(value) if value is not None else default
    except Exception:
        return default
    if v <= 0:
        return default
    return v


def _is_storage_writable(db_path: str) -> bool:
    try:
        parent = Path(db_path).resolve().parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(parent), prefix="rwcheck_", delete=True) as _:
            pass
        return True
    except Exception:
        return False


def _sse_frame(event: str, payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n"


def _extract_text_delta(stream_event: Any) -> str:
    if getattr(stream_event, "type", "") != "raw_response_event":
        return ""
    raw = getattr(stream_event, "data", None)
    if raw is None:
        return ""
    raw_type = getattr(raw, "type", "")
    if raw_type in {"response.output_text.delta", "response.refusal.delta"}:
        delta = getattr(raw, "delta", "")
        return str(delta or "")
    return ""


def create_app(config_path: str | None = None) -> FastAPI:
    resolved_config = Path(config_path or os.environ.get("AGENT_CONFIG", "agent.json")).resolve()

    app = FastAPI(title="AgentFW API", version="0.1.0")

    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def _http_exc_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        session_id = getattr(request.state, "session_id", None)
        user_id = getattr(request.state, "user_id", None)
        detail = str(exc.detail)
        mapped = _classify_error(exc.status_code, detail)
        _log_json(
            "warning",
            event="request_failed",
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            error_code=mapped["code"],
            biz_code=mapped["biz_code"],
            http_status=exc.status_code,
            detail=detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_api_err(
                request_id=request_id,
                code=mapped["code"],
                message="error",
                error_type=mapped["error_type"],
                http_status=exc.status_code,
                biz_code=mapped["biz_code"],
                user_tip=mapped["user_tip"],
                retryable=mapped["retryable"],
                action=mapped["action"],
                detail=detail,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        session_id = getattr(request.state, "session_id", None)
        user_id = getattr(request.state, "user_id", None)
        mapped = _classify_error(422, str(exc.errors()))
        _log_json(
            "warning",
            event="request_failed",
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            error_code=mapped["code"],
            biz_code=mapped["biz_code"],
            http_status=422,
            detail=str(exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content=_api_err(
                request_id=request_id,
                code=mapped["code"],
                message="error",
                error_type=mapped["error_type"],
                http_status=422,
                biz_code=mapped["biz_code"],
                user_tip=mapped["user_tip"],
                retryable=mapped["retryable"],
                action=mapped["action"],
                detail=str(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exc_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        session_id = getattr(request.state, "session_id", None)
        user_id = getattr(request.state, "user_id", None)
        mapped = _classify_error(500, str(exc))
        _log_json(
            "error",
            event="request_failed",
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            error_code=mapped["code"],
            biz_code=mapped["biz_code"],
            http_status=500,
            detail="internal server error",
        )
        return JSONResponse(
            status_code=500,
            content=_api_err(
                request_id=request_id,
                code=mapped["code"],
                message="error",
                error_type=mapped["error_type"],
                http_status=500,
                biz_code=mapped["biz_code"],
                user_tip=mapped["user_tip"],
                retryable=mapped["retryable"],
                action=mapped["action"],
                detail="internal server error",
            ),
        )

    @app.on_event("startup")
    async def _on_startup() -> None:
        cfg = load_config(str(resolved_config))
        reg = _build_registry(cfg)

        llm_cfg = cfg.get("llm", {}) or {}
        agent_cfg = cfg.get("agent", {}) or {}
        mem_cfg = cfg.get("memory", {}) or {}
        mcp_cfg = cfg.get("mcp", {}) or {}
        skills_cfg = cfg.get("skills", {}) or {}

        configure_openai(llm_cfg)

        session = build_session(mem_cfg)
        max_turns = int(agent_cfg.get("max_turns", agent_cfg.get("max_tool_steps", 10)))

        servers = build_mcp_servers(mcp_cfg)
        mcp_manager = build_mcp_manager(servers, mcp_cfg)
        active_servers: list[Any] = []
        if mcp_manager is not None:
            await mcp_manager.__aenter__()
            active_servers = mcp_manager.active_servers

        skill_store = load_skill_store(skills_cfg, config_dir=resolved_config.parent)

        app.state.runtime = AppRuntime(
            cfg=cfg,
            config_path=resolved_config,
            registry=reg,
            session=session,
            max_turns=max_turns,
            llm_cfg=llm_cfg,
            agent_cfg=agent_cfg,
            skill_store=skill_store,
            active_servers=active_servers,
            mcp_manager=mcp_manager,
        )

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        runtime: AppRuntime | None = getattr(app.state, "runtime", None)
        if runtime and runtime.mcp_manager is not None:
            await runtime.mcp_manager.__aexit__(None, None, None)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request):
        runtime: AppRuntime | None = getattr(request.app.state, "runtime", None)
        if runtime is None:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "runtime_not_ready"})

        problems: list[str] = []
        if not os.environ.get("AGENT_API_KEY", "").strip():
            problems.append("missing AGENT_API_KEY")
        if not os.environ.get("OPENAI_API_KEY", "").strip() and not os.environ.get("GEMINI_API_KEY", "").strip():
            problems.append("missing OPENAI_API_KEY or GEMINI_API_KEY")
        db_path = str((runtime.cfg.get("memory") or {}).get("db_path") or ".agent/sessions.db")
        if not _is_storage_writable(db_path):
            problems.append("memory storage not writable")
        if runtime.mcp_manager is not None and not runtime.active_servers:
            problems.append("mcp enabled but no active servers")

        if problems:
            return JSONResponse(status_code=503, content={"status": "not_ready", "problems": problems})

        return {
            "status": "ready",
            "config_path": str(runtime.config_path),
            "mcp_active_servers": len(runtime.active_servers),
        }

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        # Minimal placeholder for Prometheus integration in the next step.
        return PlainTextResponse("agentfw_up 1\n")

    @app.post("/v1/chat", response_model=ApiResponse, dependencies=[Depends(require_api_key)])
    async def chat(req: ChatRequest, request: Request) -> ApiResponse:
        runtime: AppRuntime | None = getattr(request.app.state, "runtime", None)
        if runtime is None:
            raise HTTPException(status_code=503, detail="Service is not ready.")

        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        request.state.session_id = req.session_id
        request.state.user_id = req.user_id
        start = time.perf_counter()
        timeout_s = _to_float(os.environ.get("AGENT_RUN_TIMEOUT_SECONDS"), 60.0)
        message = req.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="message must not be empty")
        _log_json(
            "info",
            event="request_received",
            request_id=request_id,
            session_id=req.session_id,
            user_id=req.user_id,
            error_code=0,
            path="/v1/chat",
        )

        try:
            agent, active_skills = runtime.agent_for_input(message)
            result = await asyncio.wait_for(
                Runner.run(
                    agent,
                    message,
                    max_turns=runtime.max_turns,
                    session=runtime.session,
                ),
                timeout=timeout_s,
            )
            answer = _format_output(result.final_output)
        except asyncio.TimeoutError as e:
            raise HTTPException(
                status_code=504,
                detail=f"chat_timeout request_id={request_id}: timeout={timeout_s}s",
            ) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"chat_failed request_id={request_id}: {e}") from e

        latency_ms = int((time.perf_counter() - start) * 1000)
        data = ChatData(
            answer=answer,
            latency_ms=latency_ms,
            session_id=req.session_id,
            user_id=req.user_id,
            tool_calls=[],
            used_skills=[s.name for s in active_skills],
        )
        _log_json(
            "info",
            event="request_succeeded",
            request_id=request_id,
            session_id=req.session_id,
            user_id=req.user_id,
            error_code=0,
            latency_ms=latency_ms,
            path="/v1/chat",
        )
        return ApiResponse(**_api_ok(request_id=request_id, data=data))

    @app.post("/v1/chat/stream", dependencies=[Depends(require_api_key)])
    async def chat_stream(req: ChatRequest, request: Request):
        runtime: AppRuntime | None = getattr(request.app.state, "runtime", None)
        if runtime is None:
            raise HTTPException(status_code=503, detail="Service is not ready.")

        message = req.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="message must not be empty")

        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        request.state.session_id = req.session_id
        request.state.user_id = req.user_id
        timeout_s = _to_float(os.environ.get("AGENT_RUN_TIMEOUT_SECONDS"), 60.0)

        async def _event_gen():
            start = time.perf_counter()
            _log_json(
                "info",
                event="request_received",
                request_id=request_id,
                session_id=req.session_id,
                user_id=req.user_id,
                error_code=0,
                path="/v1/chat/stream",
            )
            yield _sse_frame("start", {"request_id": request_id, "timestamp": _now_utc_iso()})

            try:
                agent, active_skills = runtime.agent_for_input(message)
                result = Runner.run_streamed(
                    agent,
                    message,
                    max_turns=runtime.max_turns,
                    session=runtime.session,
                )
                saw_delta = False

                async with asyncio.timeout(timeout_s):
                    async for stream_event in result.stream_events():
                        if await request.is_disconnected():
                            _log_json(
                                "warning",
                                event="client_disconnected",
                                request_id=request_id,
                                session_id=req.session_id,
                                user_id=req.user_id,
                                error_code=0,
                            )
                            return

                        delta = _extract_text_delta(stream_event)
                        if delta:
                            saw_delta = True
                            yield _sse_frame(
                                "delta",
                                {
                                    "request_id": request_id,
                                    "delta": delta,
                                },
                            )

                answer = _format_output(result.final_output)
                if answer and not saw_delta:
                    # Fallback: if provider does not emit text deltas, send final output once.
                    yield _sse_frame("delta", {"request_id": request_id, "delta": answer})

                latency_ms = int((time.perf_counter() - start) * 1000)
                data = ChatData(
                    answer=answer,
                    latency_ms=latency_ms,
                    session_id=req.session_id,
                    user_id=req.user_id,
                    tool_calls=[],
                    used_skills=[s.name for s in active_skills],
                )
                payload = _api_ok(request_id=request_id, data=data)
                _log_json(
                    "info",
                    event="request_succeeded",
                    request_id=request_id,
                    session_id=req.session_id,
                    user_id=req.user_id,
                    error_code=0,
                    latency_ms=latency_ms,
                    path="/v1/chat/stream",
                )
                yield _sse_frame("done", payload)
            except asyncio.TimeoutError:
                detail = f"chat_timeout request_id={request_id}: timeout={timeout_s}s"
                mapped = _classify_error(504, detail)
                _log_json(
                    "warning",
                    event="request_failed",
                    request_id=request_id,
                    session_id=req.session_id,
                    user_id=req.user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=504,
                    detail=detail,
                )
                yield _sse_frame(
                    "error",
                    _api_err(
                        request_id=request_id,
                        code=mapped["code"],
                        message="error",
                        error_type=mapped["error_type"],
                        http_status=504,
                        biz_code=mapped["biz_code"],
                        user_tip=mapped["user_tip"],
                        retryable=mapped["retryable"],
                        action=mapped["action"],
                        detail=detail,
                    ),
                )
            except Exception as e:
                detail = f"chat_failed request_id={request_id}: {e}"
                mapped = _classify_error(500, detail)
                _log_json(
                    "error",
                    event="request_failed",
                    request_id=request_id,
                    session_id=req.session_id,
                    user_id=req.user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=500,
                    detail=detail,
                )
                yield _sse_frame(
                    "error",
                    _api_err(
                        request_id=request_id,
                        code=mapped["code"],
                        message="error",
                        error_type=mapped["error_type"],
                        http_status=500,
                        biz_code=mapped["biz_code"],
                        user_tip=mapped["user_tip"],
                        retryable=mapped["retryable"],
                        action=mapped["action"],
                        detail=detail,
                    ),
                )
            finally:
                yield _sse_frame("end", "[DONE]")

        return StreamingResponse(
            _event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket):
        await websocket.accept()

        runtime: AppRuntime | None = getattr(app.state, "runtime", None)
        base_request_id = websocket.headers.get("X-Request-ID") or websocket.headers.get("x-request-id") or uuid.uuid4().hex
        if runtime is None:
            payload = _api_err(
                request_id=base_request_id,
                code=2001,
                message="error",
                error_type="SERVICE_NOT_READY",
                http_status=503,
                biz_code="SERVICE_NOT_READY",
                user_tip="服务尚未就绪，请稍后重试。",
                retryable=True,
                action="先调用 /readyz 确认就绪状态。",
                detail="Service is not ready.",
            )
            await websocket.send_json({"event": "error", "payload": payload})
            await websocket.close(code=1011)
            return

        raw_api_key = websocket.headers.get("x-api-key") or websocket.query_params.get("api_key")
        try:
            _validate_api_key(raw_api_key)
        except HTTPException as exc:
            mapped = _classify_error(exc.status_code, str(exc.detail))
            payload = _api_err(
                request_id=base_request_id,
                code=mapped["code"],
                message="error",
                error_type=mapped["error_type"],
                http_status=exc.status_code,
                biz_code=mapped["biz_code"],
                user_tip=mapped["user_tip"],
                retryable=mapped["retryable"],
                action=mapped["action"],
                detail=str(exc.detail),
            )
            await websocket.send_json({"event": "error", "payload": payload})
            await websocket.close(code=4401)
            return

        timeout_s = _to_float(os.environ.get("AGENT_RUN_TIMEOUT_SECONDS"), 60.0)

        while True:
            request_id = uuid.uuid4().hex
            session_id: str | None = None
            user_id: str | None = None
            try:
                incoming = await websocket.receive_json()
                if not isinstance(incoming, dict):
                    raise HTTPException(status_code=422, detail="request body must be a JSON object")

                request_id = str(incoming.get("request_id") or request_id)
                req = ChatRequest.model_validate(incoming)
                session_id = req.session_id
                user_id = req.user_id

                message = req.message.strip()
                if not message:
                    raise HTTPException(status_code=400, detail="message must not be empty")

                _log_json(
                    "info",
                    event="request_received",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=0,
                    path="/ws/chat",
                )
                await websocket.send_json({"event": "start", "request_id": request_id, "timestamp": _now_utc_iso()})

                start = time.perf_counter()
                agent, active_skills = runtime.agent_for_input(message)
                result = Runner.run_streamed(
                    agent,
                    message,
                    max_turns=runtime.max_turns,
                    session=runtime.session,
                )
                saw_delta = False

                async with asyncio.timeout(timeout_s):
                    async for stream_event in result.stream_events():
                        delta = _extract_text_delta(stream_event)
                        if delta:
                            saw_delta = True
                            await websocket.send_json(
                                {
                                    "event": "delta",
                                    "request_id": request_id,
                                    "delta": delta,
                                }
                            )

                answer = _format_output(result.final_output)
                if answer and not saw_delta:
                    await websocket.send_json({"event": "delta", "request_id": request_id, "delta": answer})

                latency_ms = int((time.perf_counter() - start) * 1000)
                data = ChatData(
                    answer=answer,
                    latency_ms=latency_ms,
                    session_id=session_id,
                    user_id=user_id,
                    tool_calls=[],
                    used_skills=[s.name for s in active_skills],
                )
                payload = _api_ok(request_id=request_id, data=data)
                _log_json(
                    "info",
                    event="request_succeeded",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=0,
                    latency_ms=latency_ms,
                    path="/ws/chat",
                )
                await websocket.send_json({"event": "done", "payload": payload})
                await websocket.send_json({"event": "end", "request_id": request_id, "done": True})
            except WebSocketDisconnect:
                _log_json(
                    "warning",
                    event="client_disconnected",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=0,
                    path="/ws/chat",
                )
                return
            except ValidationError as e:
                mapped = _classify_error(422, str(e.errors()))
                _log_json(
                    "warning",
                    event="request_failed",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=422,
                    detail=str(e.errors()),
                )
                payload = _api_err(
                    request_id=request_id,
                    code=mapped["code"],
                    message="error",
                    error_type=mapped["error_type"],
                    http_status=422,
                    biz_code=mapped["biz_code"],
                    user_tip=mapped["user_tip"],
                    retryable=mapped["retryable"],
                    action=mapped["action"],
                    detail=str(e.errors()),
                )
                await websocket.send_json({"event": "error", "payload": payload})
                await websocket.send_json({"event": "end", "request_id": request_id, "done": True})
            except asyncio.TimeoutError:
                detail = f"chat_timeout request_id={request_id}: timeout={timeout_s}s"
                mapped = _classify_error(504, detail)
                _log_json(
                    "warning",
                    event="request_failed",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=504,
                    detail=detail,
                )
                payload = _api_err(
                    request_id=request_id,
                    code=mapped["code"],
                    message="error",
                    error_type=mapped["error_type"],
                    http_status=504,
                    biz_code=mapped["biz_code"],
                    user_tip=mapped["user_tip"],
                    retryable=mapped["retryable"],
                    action=mapped["action"],
                    detail=detail,
                )
                await websocket.send_json({"event": "error", "payload": payload})
                await websocket.send_json({"event": "end", "request_id": request_id, "done": True})
            except HTTPException as e:
                mapped = _classify_error(e.status_code, str(e.detail))
                _log_json(
                    "warning",
                    event="request_failed",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=e.status_code,
                    detail=str(e.detail),
                )
                payload = _api_err(
                    request_id=request_id,
                    code=mapped["code"],
                    message="error",
                    error_type=mapped["error_type"],
                    http_status=e.status_code,
                    biz_code=mapped["biz_code"],
                    user_tip=mapped["user_tip"],
                    retryable=mapped["retryable"],
                    action=mapped["action"],
                    detail=str(e.detail),
                )
                await websocket.send_json({"event": "error", "payload": payload})
                await websocket.send_json({"event": "end", "request_id": request_id, "done": True})
            except Exception as e:
                detail = f"chat_failed request_id={request_id}: {e}"
                mapped = _classify_error(500, detail)
                _log_json(
                    "error",
                    event="request_failed",
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    error_code=mapped["code"],
                    biz_code=mapped["biz_code"],
                    http_status=500,
                    detail=detail,
                )
                payload = _api_err(
                    request_id=request_id,
                    code=mapped["code"],
                    message="error",
                    error_type=mapped["error_type"],
                    http_status=500,
                    biz_code=mapped["biz_code"],
                    user_tip=mapped["user_tip"],
                    retryable=mapped["retryable"],
                    action=mapped["action"],
                    detail=detail,
                )
                await websocket.send_json({"event": "error", "payload": payload})
                await websocket.send_json({"event": "end", "request_id": request_id, "done": True})

    return app


app = create_app()
