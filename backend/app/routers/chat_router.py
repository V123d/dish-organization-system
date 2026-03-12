"""
走云智能排菜系统 — 对话路由

处理 /api/chat/* 相关请求，包括 SSE 流式排菜对话。
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..schemas.chat_schema import ChatRequest
from ..services.orchestrator import orchestrate_menu_stream

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/send")
async def chat_send(request: ChatRequest):
    """
    智能排菜对话接口 (SSE)

    接收用户消息和完整的规则配置 JSON，触发多智能体编排流程，
    以 Server-Sent Events 格式流式返回思考进度和菜单结果。
    """
    return StreamingResponse(
        orchestrate_menu_stream(request.message, request.config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
