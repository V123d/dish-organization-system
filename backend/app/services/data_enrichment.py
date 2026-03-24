"""
走云智能排菜系统 — 数据补全智能体

职责：将 LLM 返回的紧凑格式菜单（仅 {id, name}）补全为包含完整属性的菜品数据。
"""
import logging
from typing import Any
from sqlalchemy import select

from .base_agent import BaseAgent
from ..database import AsyncSessionLocal
from ..models.dish import Dish

logger = logging.getLogger(__name__)

# 重新导出 DataEnrichmentAgent 等，保持与之前接口一致
__all__ = ["DataEnrichmentAgent", "search_dishes"]


class DataEnrichmentAgent(BaseAgent):
    """数据补全智能体（纯 Python，不调用 LLM）"""

    agent_id = "data-enrichment"
    agent_name = "Data Enrichment / 数据补全智能体"
    agent_description = "将 AI 生成的紧凑菜单（仅含菜品 ID 和名称）补全为包含食材、营养、成本等完整属性的菜品数据"
    agent_type = "rule"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        menu: dict = kwargs.get("menu", {})
        enriched_menu = await _enrich_menu_data(menu)
        return {"success": True, "menu": enriched_menu}


async def _enrich_menu_data(menu: dict) -> dict:
    """
    将 LLM 返回的紧凑格式补全为前端需要的完整菜品数据（异步从数据库查询）。
    """
    dish_ids = set()
    for date, meals in menu.items():
        for meal_name, categories in meals.items():
            for cat_name, dishes in categories.items():
                for dish in dishes:
                    if dish.get("id"):
                        dish_ids.add(dish["id"])

    dish_index = {}
    if dish_ids:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Dish).where(Dish.id.in_(list(dish_ids))))
            dishes_objs = result.scalars().all()
            for d in dishes_objs:
                dish_index[d.id] = {
                    "id": d.id,
                    "name": d.name,
                    "category": d.category,
                    "ingredients_quantified": d.ingredients_quantified,
                    "applicable_meals": d.applicable_meals,
                    "flavor": d.flavor,
                    "cost_per_serving": d.cost_per_serving,
                    "nutrition": d.nutrition,
                    "tags": d.tags,
                }

    enriched: dict = {}
    for date, meals in menu.items():
        enriched[date] = {}
        for meal_name, categories in meals.items():
            enriched[date][meal_name] = {}
            for cat_name, dishes in categories.items():
                enriched_dishes = []
                for dish in dishes:
                    dish_id = dish.get("id")
                    if dish_id and dish_id in dish_index:
                        enriched_dishes.append(dish_index[dish_id])
                    else:
                        # 未找到对应 ID，保留 LLM 原始数据并补充默认值
                        enriched_dishes.append({
                            "id": dish_id or 0,
                            "name": dish.get("name", "未知菜品"),
                            "category": cat_name,
                            "ingredients_quantified": dish.get("ingredients_quantified", []),
                            "applicable_meals": dish.get("applicable_meals", []),
                            "flavor": dish.get("flavor", ""),
                            "cost_per_serving": dish.get("cost_per_serving", 0),
                            "nutrition": dish.get("nutrition", {
                                "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
                            }),
                            "tags": dish.get("tags", []),
                        })
                enriched[date][meal_name][cat_name] = enriched_dishes
    return enriched


async def search_dishes(query: str) -> list[dict[str, Any]]:
    """
    搜索菜品库（数据库实现）。
    """
    query_lower = query.lower()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Dish).where(
                Dish.name.ilike(f"%{query_lower}%") |
                Dish.category.ilike(f"%{query_lower}%")
            ).limit(20)
        )
        dishes = result.scalars().all()
        
        return [
            {
                "id": d.id,
                "name": d.name,
                "category": d.category,
                "ingredients_quantified": d.ingredients_quantified,
                "applicable_meals": d.applicable_meals,
                "flavor": d.flavor,
                "cost_per_serving": d.cost_per_serving,
                "nutrition": d.nutrition,
                "tags": d.tags,
            } for d in dishes
        ]
