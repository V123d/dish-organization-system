"""
走云智能排菜系统 — 多智能体编排器

职责：串联 4 个独立智能体的执行流程，以 SSE 事件流形式返回给前端。
调用链：Intent Parser → Menu Generator (流式) → Constraint Checker → Data Enrichment

当约束校验不通过时，自动触发 Menu Generator 重新生成（最多重试 MAX_RETRIES 次）。
"""
import json
import asyncio
import logging
from typing import AsyncGenerator

from ..schemas.chat_schema import MenuPlanConfig
from .base_agent import AgentRegistry

logger = logging.getLogger(__name__)

MAX_RETRIES = 2  # 校验不通过时最多重排次数


async def orchestrate_menu_stream(
    user_message: str,
    config: MenuPlanConfig,
) -> AsyncGenerator[str, None]:
    """
    编排 4 个智能体，以 SSE 事件流返回全流程进度。

    事件类型：
    - thinking: 各阶段进度更新
    - content:  文本内容流
    - menu_result: 最终菜单结果
    - error:    错误信息
    """
    intent_agent = AgentRegistry.get("intent-parser")
    menu_agent = AgentRegistry.get("menu-generator")
    checker_agent = AgentRegistry.get("constraint-checker")
    enrichment_agent = AgentRegistry.get("data-enrichment")

    if not all([intent_agent, menu_agent, checker_agent, enrichment_agent]):
        yield _sse("error", {"message": "智能体初始化失败：部分智能体未注册"})
        yield "data: [DONE]\n\n"
        return

    config_json = config.model_dump_json(indent=None)
    config_dict = config.model_dump()

    # ===== Step 1: 意图解析 =====
    yield _sse("thinking", {"step": {"label": "意图解析", "status": "running", "detail": "正在理解您的排菜需求..."}})

    intent_result = await intent_agent.execute(  # type: ignore[union-attr]
        user_message=user_message,
        config_json=config_json,
    )

    if not intent_result.get("success"):
        yield _sse("thinking", {"step": {"label": "意图解析", "status": "error", "detail": intent_result.get("error", "解析失败")}})
        intent_summary = user_message  # 降级：直接使用原始消息
    else:
        parsed = intent_result.get("parsed_intent", {})
        intent_summary = parsed.get("summary", user_message)
        yield _sse("thinking", {"step": {"label": "意图解析", "status": "done", "detail": f"已解析: {intent_summary[:50]}"}})

    # ===== Step 2: 菜单生成 (流式) =====
    menu_data = None
    summary_text = ""

    for attempt in range(1 + MAX_RETRIES):
        attempt_label = f"菜单生成" if attempt == 0 else f"菜单重排 (第{attempt}次)"
        yield _sse("thinking", {"step": {"label": attempt_label, "status": "running", "detail": "正在调用 AI 生成菜单..."}})

        try:
            # 使用流式生成，每 50 token 发送心跳
            raw_content = ""
            token_count = 0
            async for content, count in menu_agent.execute_stream(  # type: ignore[union-attr]
                config=config,
                user_message=user_message,
                intent_summary=intent_summary,
            ):
                raw_content = content
                token_count = count
                if token_count % 50 == 0:
                    yield _sse("thinking", {"step": {
                        "label": attempt_label,
                        "status": "running",
                        "detail": f"AI 正在生成中... 已接收 {token_count} tokens",
                    }})

            logger.info(f"LLM response length: {len(raw_content)}, tokens: {token_count}")

            # 解析 JSON
            parsed_menu = _extract_json(raw_content)
            if parsed_menu and "menu" in parsed_menu:
                menu_data = parsed_menu["menu"]
                summary_text = parsed_menu.get("summary", "菜单已生成")
                yield _sse("thinking", {"step": {"label": attempt_label, "status": "done", "detail": f"菜单 JSON 已生成 ({token_count} tokens)"}})
            else:
                logger.warning(f"Menu parse failed. Raw first 200: {raw_content[:200]}")
                yield _sse("thinking", {"step": {"label": attempt_label, "status": "error", "detail": "AI 返回格式异常"}})
                if attempt == MAX_RETRIES:
                    yield _sse("content", {"content": f"⚠️ AI 返回格式异常，原始内容：\n\n{raw_content[:500]}"})
                    yield "data: [DONE]\n\n"
                    return
                continue

        except Exception as e:
            logger.exception("Menu generation failed")
            yield _sse("thinking", {"step": {"label": attempt_label, "status": "error", "detail": str(e)[:80]}})
            yield _sse("error", {"message": f"菜单生成智能体调用失败: {str(e)}"})
            yield "data: [DONE]\n\n"
            return

        # ===== Step 3: 约束校验 =====
        yield _sse("thinking", {"step": {"label": "约束校验", "status": "running", "detail": "正在交叉校验红线与预算..."}})

        check_result = await checker_agent.execute(  # type: ignore[union-attr]
            menu=menu_data,
            config=config_dict,
        )
        metrics = check_result.get("metrics", {})

        if check_result.get("passed"):
            yield _sse("thinking", {"step": {"label": "约束校验", "status": "done", "detail": f"校验通过 ✓ 重复率 {metrics.get('repeat_rate', 0)}%"}})
            break  # 校验通过，跳出重试循环
        else:
            alert_count = len(check_result.get("alerts", []))
            if attempt < MAX_RETRIES:
                yield _sse("thinking", {"step": {"label": "约束校验", "status": "error", "detail": f"发现 {alert_count} 条告警，准备重新排菜..."}})
                await asyncio.sleep(0.3)
            else:
                # 最后一次仍未通过，带告警输出
                yield _sse("thinking", {"step": {"label": "约束校验", "status": "done", "detail": f"⚠️ 仍有 {alert_count} 条告警，已输出最佳结果"}})

    if not menu_data:
        yield _sse("error", {"message": "菜单生成失败"})
        yield "data: [DONE]\n\n"
        return

    # ===== Step 4: 数据补全 =====
    yield _sse("thinking", {"step": {"label": "数据补全", "status": "running", "detail": "正在补全菜品详细信息..."}})

    enrich_result = await enrichment_agent.execute(menu=menu_data)  # type: ignore[union-attr]
    enriched_menu = enrich_result.get("menu", menu_data)

    yield _sse("thinking", {"step": {"label": "数据补全", "status": "done", "detail": "菜品信息已补全 ✓"}})

    # 合并指标（补上营养分数的默认值）
    final_metrics = {
        "total_cost": metrics.get("total_cost", 0),
        "avg_nutrition_score": metrics.get("avg_nutrition_score", 85),
        "repeat_rate": metrics.get("repeat_rate", 0),
        "alert_count": metrics.get("alert_count", 0),
    }

    # 发送结果
    yield _sse("content", {"content": f"✅ {summary_text}\n\n已为您安排好一周菜单，请在左侧日历看板中查看详情。"})
    yield _sse("menu_result", {"menu": enriched_menu, "metrics": final_metrics})
    yield "data: [DONE]\n\n"


def _sse(event_type: str, data: dict) -> str:
    """构造 SSE 事件字符串"""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_json(text: str) -> dict | None:
    """从 LLM 返回文本中提取 JSON 对象"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start: end + 1])
        except json.JSONDecodeError:
            pass
    return None
