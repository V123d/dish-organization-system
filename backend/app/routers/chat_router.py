"""
走云智能排菜系统 — 对话路由

处理 /api/chat/* 相关请求，包括 SSE 流式排菜对话。
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ..schemas.chat_schema import ChatRequest, ChatSessionCreate, ChatSessionItem, ChatSessionDetail
from ..services.orchestrator import orchestrate_menu_stream
from ..database import get_db, AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, desc
import uuid
import json
from ..models.chat_session import ChatSession
from ..models.user import User
from ..security import get_current_active_user as get_current_user
from openai import AsyncOpenAI
from ..config import LLM_API_KEY, LLM_API_URL, LLM_MODEL

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/send")
async def chat_send(request: ChatRequest):
    """
    智能排菜对话接口 (SSE)

    接收用户消息和完整的规则配置 JSON，触发多智能体编排流程，
    以 Server-Sent Events 格式流式返回思考进度和菜单结果。
    """
    return StreamingResponse(
        orchestrate_menu_stream(request.message, request.config, request.current_menu, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions")
async def save_chat_session(
    data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存或更新对话会话，新建时自动取标题"""
    session_id = data.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        
        # 提取第一条用户消息以生成标题
        first_user_msg = ""
        for msg in data.messages:
            if msg.get("role") == "user":
                first_user_msg = msg.get("content", "")
                break
                
        title = "新对话"
        if first_user_msg:
            # 简单调用 LLM 生成标题
            try:
                client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_URL)
                resp = await client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个标题生成助手。请根据用户的输入，总结一个不多于7个字的简短中文标题。"},
                        {"role": "user", "content": first_user_msg[:100]}
                    ],
                    temperature=0.3,
                    max_tokens=20
                )
                title = resp.choices[0].message.content.strip() if resp.choices else "新对话"
            except Exception:
                pass

        new_session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=title,
            messages=data.messages
        )
        db.add(new_session)
        await db.commit()
        return {"success": True, "session_id": session_id, "title": title}
    else:
        # 更新现有 session
        res = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
        session_obj = res.scalar_one_or_none()
        if not session_obj:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # 将对象设为已修改状态以触发 updated_at 更新
        session_obj.messages = data.messages
        await db.commit()
        return {"success": True, "session_id": session_id, "title": session_obj.title}


@router.get("/sessions")
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的对话列表"""
    res = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.updated_at))
    )
    sessions = res.scalars().all()
    out = []
    for s in sessions:
        out.append(ChatSessionItem(
            id=s.id,
            title=s.title,
            updated_at=s.updated_at.isoformat() if s.updated_at else ""
        ))
    return {"success": True, "sessions": out}


@router.get("/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定对话的完整内容"""
    res = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True, "data": ChatSessionDetail(
        id=s.id,
        title=s.title,
        messages=s.messages,
        updated_at=s.updated_at.isoformat() if s.updated_at else ""
    )}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定对话"""
    res = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.delete(s)
    await db.commit()
    return {"success": True}
