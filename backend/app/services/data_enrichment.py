"""
走云智能排菜系统 — 数据补全智能体

职责：将 LLM 返回的紧凑格式菜单（仅 {id, name}）补全为包含完整属性的菜品数据。
同时提供菜品搜索功能。
"""
import logging
from typing import Any

from .base_agent import BaseAgent
from .menu_generator import DISH_LIBRARY

logger = logging.getLogger(__name__)

# 构建菜品 ID → 完整数据的索引
_DISH_INDEX: dict[int, dict] = {d["id"]: d for d in DISH_LIBRARY}


class DataEnrichmentAgent(BaseAgent):
    """数据补全智能体（纯 Python，不调用 LLM）"""

    agent_id = "data-enrichment"
    agent_name = "Data Enrichment / 数据补全智能体"
    agent_description = "将 AI 生成的紧凑菜单（仅含菜品 ID 和名称）补全为包含食材、营养、成本等完整属性的菜品数据"
    agent_type = "rule"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行数据补全。

        Args:
            menu: 紧凑格式的菜单 JSON

        Returns:
            包含完整菜品属性的丰富菜单 JSON
        """
        menu: dict = kwargs.get("menu", {})
        enriched_menu = _enrich_menu_data(menu)
        return {"success": True, "menu": enriched_menu}


def _enrich_menu_data(menu: dict) -> dict:
    """
    将 LLM 返回的紧凑格式补全为前端需要的完整菜品数据。

    为什么需要这一步：
    LLM 输出一周完整菜品属性的 JSON 容易超过 max_tokens 导致截断。
    因此让 LLM 只输出 {id, name}，后端根据 id 从菜品库中查找并补全
    category/ingredients/nutrition 等完整属性。
    """
    enriched: dict = {}
    for date, meals in menu.items():
        enriched[date] = {}
        for meal_name, categories in meals.items():
            enriched[date][meal_name] = {}
            for cat_name, dishes in categories.items():
                enriched_dishes = []
                for dish in dishes:
                    dish_id = dish.get("id")
                    if dish_id and dish_id in _DISH_INDEX:
                        enriched_dishes.append(dict(_DISH_INDEX[dish_id]))
                    else:
                        fallback = {
                            "id": dish_id or 0,
                            "name": dish.get("name", "未知菜品"),
                            "category": cat_name,
                            "main_ingredients": dish.get("main_ingredients", []),
                            "process_type": dish.get("process_type", ""),
                            "flavor": dish.get("flavor", ""),
                            "cost_per_serving": dish.get("cost_per_serving", 0),
                            "nutrition": dish.get("nutrition", {
                                "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
                            }),
                            "tags": dish.get("tags", []),
                        }
                        enriched_dishes.append(fallback)
                enriched[date][meal_name][cat_name] = enriched_dishes
    return enriched


def search_dishes(query: str) -> list[dict]:
    """搜索菜品库（简单关键词匹配）"""
    query_lower = query.lower()
    results = []
    for dish in DISH_LIBRARY:
        if (
            query_lower in dish["name"].lower()
            or any(query_lower in ing.lower() for ing in dish["main_ingredients"])
            or any(query_lower in tag.lower() for tag in dish.get("tags", []))
            or query_lower in dish.get("category", "").lower()
        ):
            results.append(dish)
    return results[:20]
