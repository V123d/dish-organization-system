"""
走云智能排菜系统 — 意图解析智能体

职责：接收用户自然语言指令 + 结构化配置 JSON，解析出排菜意图摘要。
输出：结构化的排菜需求 JSON。
"""
import logging
from typing import Any
from pydantic import BaseModel, Field

from openai import AsyncOpenAI
import httpx

from ..config import LLM_API_URL, LLM_API_KEY, LLM_MODEL
from .base_agent import BaseAgent
from .utils import extract_json

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_API_URL,
    timeout=httpx.Timeout(60.0, connect=10.0),
)

class DailyOverride(BaseModel):
    flavor: str = Field(default="", description="当日整体口味偏好，如清淡、辣")
    preferred_ingredients: list[str] = Field(default_factory=list, description="当日偏好食材")
    avoid_ingredients: list[str] = Field(default_factory=list, description="当日避开食材")
    special_requests: list[str] = Field(default_factory=list, description="当日其他特殊限定要求")

class MealOverride(BaseModel):
    target: str = Field(description="目标餐次，格式为 '星期几-餐次名'，如 '星期一-午餐' 或全局的 '午餐'")
    category_changes: dict[str, int] = Field(default_factory=dict, description="分类数量绝对值修改，如 {'汤': 0, '荤菜': 2} 代表不喝汤，荤菜变2个")
    budget_override: float | None = Field(default=None, description="特定餐次预算修改")

class RegenerateTarget(BaseModel):
    date: str = Field(description="目标日期，格式为 YYYY-MM-DD")
    meal_name: str = Field(description="目标餐次，例如 '早餐', '午餐', '晚餐'")

class ParsedIntentDef(BaseModel):
    action: str = Field(default="生成菜单", description="当前意图类型")
    summary: str = Field(description="一句话总结用户核心诉求")
    global_preferences: list[str] = Field(default_factory=list, description="全局偏好关键词")
    budget_override: float | None = Field(default=None, description="全局预算覆盖")
    include_weekends: bool = Field(default=False, description="是否显式要求包含周末")
    daily_overrides: dict[str, DailyOverride] = Field(default_factory=dict, description="按天特别定制，key严格为星期一、星期二等")
    meal_overrides: list[MealOverride] = Field(default_factory=list, description="对具体某餐的分类或规则修改")
    regenerate_targets: list[RegenerateTarget] = Field(default_factory=list, description="局部修改时需要彻底重新生成的特定日期和餐次")

# 精简 prompt，减少 token 消耗
INTENT_SYSTEM_PROMPT = """你是排菜系统的意图解析智能体。将用户排菜指令解析为标准摘要，并支持强大的局部系统规则覆写（Mutation）。
严格输出如下结构的 JSON（无其他文字），如果有不需要填写的字段，保留为空列表/空对象/null：
{
  "parsed_intent": {
    "action": "生成菜单",
    "summary": "一句话总结用户的核心诉求",
    "global_preferences": ["降温驱寒", "高蛋白"],
    "budget_override": null,
    "include_weekends": false,
    "daily_overrides": {
      "星期一": {"flavor": "清淡", "preferred_ingredients": [], "avoid_ingredients": [], "special_requests": []}
    },
    "meal_overrides": [
      {"target": "星期三-午餐", "category_changes": {"汤": 0, "荤菜": 2}, "budget_override": null}
    ],
    "regenerate_targets": [
      {"date": "2026-03-24", "meal_name": "晚餐"}
    ]
  }
}

说明：
- global_preferences：全局口味或偏好
- daily_overrides：针对特定星期几的独立要求，键名严格为 "星期一" 等。
- meal_overrides：修改特定餐次结构。target 为 "午餐" (全局) 或 "星期三-晚餐" (特定天)。category_changes 表示将指定分类的数量强行改为某个数值（如设为0即删除该分类）。
- include_weekends：如果用户明示要排每一天、包含周末或七天等，设为 true。
- regenerate_targets：若上下文中已存在菜单且用户要求修改某一天/某一餐的内容（如“把明天的晚餐换一下”），请在此精确指出需要重新生成的日期和餐次（若未指明餐次则默认全天所有餐次逐一列出）。为空列表则表示全量重新排餐或未指定。"""


class IntentParserAgent(BaseAgent):
    """意图解析智能体"""

    agent_id = "intent-parser"
    agent_name = "Intent Parser / 意图解析智能体"
    agent_description = "将用户自然语言排菜指令解析为结构化排菜需求，提取特殊偏好、预算要求和食材偏好"
    agent_type = "llm"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行意图解析。

        Args:
            user_message: 用户自然语言消息
            config_json:  结构化配置 JSON 字符串（用于获取周期、餐次等上下文）

        Returns:
            {success: bool, parsed_intent: dict}
        """
        user_message: str = kwargs.get("user_message", "")
        config_json: str = kwargs.get("config_json", "{}")
        current_menu_json: str = kwargs.get("current_menu_json", "")
        history: list[dict] = kwargs.get("history", [])

        user_prompt = f"用户指令：{user_message}\n当前配置（摘要）：{config_json[:500]}"
        if current_menu_json:
            user_prompt += f"\n当前已有完整菜单（局部修改参考，请根据需求推导需重新生成的日期）：\n{current_menu_json[:1500]}"

        llm_messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]
        for msg in history:
            role = "user" if msg.get("role") == "user" else "assistant"
            llm_messages.append({"role": role, "content": msg.get("content", "")})
        llm_messages.append({"role": "user", "content": user_prompt})

        try:
            response = await _client.chat.completions.create(
                model=LLM_MODEL,
                messages=llm_messages,
                temperature=0.2,
                max_tokens=500,  # 意图解析输出短，无需大 token 限制
            )
            raw = response.choices[0].message.content or ""
            parsed = extract_json(raw)
            if parsed and "parsed_intent" in parsed:
                try:
                    intent_obj = ParsedIntentDef(**parsed["parsed_intent"])
                    return {"success": True, "parsed_intent": intent_obj.model_dump()}
                except Exception as valid_e:
                    logger.warning(f"Intent validation fallback: {valid_e}")
                    return {"success": True, **parsed}
            else:
                # 解析失败降级：直接使用用户原始消息作为 summary
                return {
                    "success": True,
                    "parsed_intent": {
                        "action": "生成菜单",
                        "summary": user_message,
                        "global_preferences": [],
                        "budget_override": None,
                        "include_weekends": False,
                        "daily_overrides": {},
                        "meal_overrides": [],
                        "regenerate_targets": [],
                    },
                }
        except Exception as e:
            logger.exception("Intent parser failed")
            return {"success": False, "error": str(e)}
