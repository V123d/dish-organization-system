"""
走云智能排菜系统 — 菜单生成智能体

职责：根据结构化排菜需求 + 菜品库，生成一周菜单。
输出：紧凑格式的菜单 JSON（每道菜仅 {id, name}，后续由数据补全智能体补全）。
"""
import json
import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
import httpx

from ..config import LLM_API_URL, LLM_API_KEY, LLM_MODEL, DISH_LIBRARY_PATH
from ..schemas.chat_schema import MenuPlanConfig
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_API_URL,
    timeout=httpx.Timeout(120.0, connect=10.0),
)


def _load_dish_library() -> list[dict]:
    """从 JSON 文件加载菜品库"""
    try:
        with open(DISH_LIBRARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load dish library: {e}")
        return []


DISH_LIBRARY: list[dict] = _load_dish_library()


def build_menu_system_prompt(config: MenuPlanConfig, intent_summary: str = "") -> str:
    """
    构建菜单生成专用的 System Prompt。

    为什么将菜品库全量注入 Prompt：
    让 LLM 仅从已知菜品中选择，避免"幻觉菜品"，保证每道菜都能在菜品库中找到 ID。
    """
    enabled_meals = [m for m in config.meals_config if m.enabled]

    active_health = [
        h.model_dump() for h in config.global_hard_constraints.health_conditions if h.enabled
    ]
    active_dietary = [
        d.model_dump() for d in config.global_hard_constraints.dietary_restrictions if d.enabled
    ]

    meals_desc = []
    for meal in enabled_meals:
        cats = ", ".join(
            [f"{c.name}×{c.count}" for c in meal.dish_structure.categories]
        )
        meals_desc.append(
            f"  - {meal.meal_name}: {meal.diners_count}人, 餐标¥{meal.budget_per_person}/人, "
            f"分类结构=[{cats}], 主食要求={meal.staple_types}, "
            f"汤性={meal.soup_requirements.soup_property}, "
            f"必用食材={meal.meal_specific_constraints.required_ingredients}, "
            f"必排菜品={meal.meal_specific_constraints.mandatory_dishes}, "
            f"口味偏好={meal.flavor_preferences or '无特殊'}"
        )

    dishes_by_category: dict[str, list[str]] = {}
    for d in DISH_LIBRARY:
        cat = d["category"]
        if cat not in dishes_by_category:
            dishes_by_category[cat] = []
        tags_str = ",".join(d.get("tags", []))
        dishes_by_category[cat].append(
            f'{d["name"]}(id:{d["id"]}, 工艺:{d["process_type"]}, 成本:¥{d["cost_per_serving"]}, 标签:[{tags_str}])'
        )

    dishes_text = ""
    for cat, items in dishes_by_category.items():
        dishes_text += f"\n【{cat}】\n" + "\n".join(f"  - {item}" for item in items)

    return f"""你是走云智能排菜系统的菜单生成智能体。根据排菜需求从菜品库中选菜，生成一周菜单。

## 排餐环境
- 场景: {config.context_overview.scene}
- 城市: {config.context_overview.city}
- 排餐周期: {config.context_overview.schedule.start_date} 至 {config.context_overview.schedule.end_date}

## 意图摘要
{intent_summary if intent_summary else "按默认配置排菜"}

## 餐次配置
{chr(10).join(meals_desc)}

## 全局红线 (绝对禁止出现的食材)
{config.global_hard_constraints.red_lines if config.global_hard_constraints.red_lines else '无'}

## 特殊人群健康状态
{json.dumps(active_health, ensure_ascii=False) if active_health else '无'}

## 饮食禁忌
{json.dumps(active_dietary, ensure_ascii=False) if active_dietary else '无'}

## 可用菜品库
{dishes_text}

## 排菜规则 (严格遵守)
1. 每个餐次的每一天，必须严格按照分类结构配置的数量选菜。
2. 同一天的不同餐次之间，菜品不得重复。
3. 一周内同一餐次的同一分类下，菜品尽量不重复（重复率 ≤ 20%）。
4. 必须使用"必用食材"中指定的食材（优先选含该食材的菜品）。
5. 必须在指定日期安排"必排菜品"。
6. 全局红线中的食材对应的菜品绝对不能出现。
7. 注意成本控制，单人餐标不得超出预算。
8. 汤性要求必须与汤品标签匹配。

## 输出格式 (严格 JSON)
请直接输出以下格式的 JSON（不要任何其他文字）。
**每道菜只需输出 id 和 name 两个字段。**

```json
{{
  "menu": {{
    "YYYY-MM-DD": {{
      "餐次名": {{
        "分类名": [
          {{"id": 菜品ID, "name": "菜品名"}}
        ]
      }}
    }}
  }},
  "summary": "一句话排菜总结"
}}
```
"""


class MenuGeneratorAgent(BaseAgent):
    """菜单生成智能体"""

    agent_id = "menu-generator"
    agent_name = "Menu Generator / 菜单生成智能体"
    agent_description = "根据结构化排菜需求，从菜品库中选菜组装一周菜单，严格遵守分类数量、预算、红线等约束规则"
    agent_type = "llm"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行菜单生成。

        Args:
            config:         MenuPlanConfig 对象
            user_message:   用户原始消息
            intent_summary: 意图解析摘要（可选）

        Returns:
            包含 menu 和 summary 的字典
        """
        config: MenuPlanConfig = kwargs["config"]
        user_message: str = kwargs.get("user_message", "帮我排下周菜单")
        intent_summary: str = kwargs.get("intent_summary", "")

        system_prompt = build_menu_system_prompt(config, intent_summary)

        try:
            response = await _client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=8000,
            )
            raw = response.choices[0].message.content or ""
            parsed = _extract_json(raw)
            if parsed and "menu" in parsed:
                return {
                    "success": True,
                    "menu": parsed["menu"],
                    "summary": parsed.get("summary", "菜单已生成"),
                }
            else:
                logger.warning(f"Menu generator: invalid JSON. First 200 chars: {raw[:200]}")
                return {"success": False, "error": "AI 返回格式异常", "raw": raw[:500]}
        except Exception as e:
            logger.exception("Menu generator failed")
            return {"success": False, "error": str(e)}

    async def execute_stream(self, **kwargs: Any) -> AsyncGenerator[tuple[str, int], None]:
        """
        流式执行菜单生成——逐 token 接收 LLM 输出。

        Yields:
            (累积的原始文本, 当前 token 计数)
        """
        config: MenuPlanConfig = kwargs["config"]
        user_message: str = kwargs.get("user_message", "帮我排下周菜单")
        intent_summary: str = kwargs.get("intent_summary", "")

        system_prompt = build_menu_system_prompt(config, intent_summary)

        stream = await _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=8000,
            stream=True,
        )

        raw_content = ""
        token_count = 0
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                raw_content += delta.content
                token_count += 1
                yield raw_content, token_count


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
