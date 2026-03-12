"""
走云智能排菜系统 — 意图解析智能体

职责：接收用户自然语言指令 + 结构化配置 JSON，解析出排菜意图。
输出：结构化的排菜需求 JSON。
"""
import json
import logging
from typing import Any

from openai import AsyncOpenAI
import httpx

from ..config import LLM_API_URL, LLM_API_KEY, LLM_MODEL
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# LLM 客户端（与其他 LLM 智能体共享配置，但逻辑独立）
_client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_API_URL,
    timeout=httpx.Timeout(60.0, connect=10.0),
)

INTENT_SYSTEM_PROMPT = """你是走云智能排菜系统的意图解析智能体。你的唯一任务是：
将用户的自然语言排菜指令，结合提供的结构化配置信息，解析为标准化的排菜需求摘要。

你必须严格输出以下 JSON 格式（不要附加任何其他文字）：
```json
{
  "parsed_intent": {
    "action": "生成菜单",
    "period": {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"},
    "target_meals": ["午餐", "晚餐"],
    "special_preferences": ["降温驱寒", "高蛋白"],
    "budget_override": null,
    "ingredient_preferences": {"preferred": ["鸡肉"], "avoided": ["猪肉"]},
    "summary": "一句话总结用户意图"
  }
}
```

注意：
- period / target_meals 从配置中提取
- special_preferences 从用户自然语言中提取偏好关键词
- budget_override 仅当用户明确提出新预算时填写（数字），否则为 null
- ingredient_preferences 从用户语言中提取食材偏好
"""


class IntentParserAgent(BaseAgent):
    """意图解析智能体"""

    agent_id = "intent-parser"
    agent_name = "Intent Parser / 意图解析智能体"
    agent_description = "将用户自然语言排菜指令解析为结构化排菜需求，提取排餐周期、目标餐次、特殊偏好、预算要求和食材偏好"
    agent_type = "llm"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行意图解析。

        Args:
            user_message: 用户自然语言消息
            config_json:  结构化配置 JSON 字符串

        Returns:
            包含 parsed_intent 的字典
        """
        user_message: str = kwargs.get("user_message", "")
        config_json: str = kwargs.get("config_json", "{}")

        user_prompt = (
            f"用户指令：{user_message}\n\n"
            f"当前配置：\n{config_json}"
        )

        try:
            response = await _client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            raw = response.choices[0].message.content or ""
            parsed = _extract_json(raw)
            if parsed and "parsed_intent" in parsed:
                return {"success": True, **parsed}
            else:
                return {
                    "success": True,
                    "parsed_intent": {
                        "action": "生成菜单",
                        "summary": user_message,
                        "special_preferences": [],
                        "budget_override": None,
                        "ingredient_preferences": {"preferred": [], "avoided": []},
                    },
                }
        except Exception as e:
            logger.exception("Intent parser failed")
            return {"success": False, "error": str(e)}


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
