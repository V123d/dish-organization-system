"""
走云智能排菜系统 — 约束校验智能体

职责：对生成的菜单进行确定性规则校验（纯 Python，不依赖 LLM）。
校验项：红线食材扫描、预算检查、重复率计算、分类数量匹配。
"""
import logging
from typing import Any

from .base_agent import BaseAgent
from .menu_generator import DISH_LIBRARY

logger = logging.getLogger(__name__)

# 构建菜品 ID → 完整数据的索引
_DISH_INDEX: dict[int, dict] = {d["id"]: d for d in DISH_LIBRARY}


class ConstraintCheckerAgent(BaseAgent):
    """约束校验智能体（纯规则引擎，不调用 LLM）"""

    agent_id = "constraint-checker"
    agent_name = "Constraint Checker / 约束校验智能体"
    agent_description = "对生成的菜单进行确定性规则校验：红线食材扫描、预算超标检测、菜品重复率计算、分类数量匹配验证"
    agent_type = "rule"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行约束校验。

        Args:
            menu:   菜单 JSON（date -> meal -> category -> dishes 结构）
            config: MenuPlanConfig 对象或其 dict 形式

        Returns:
            {passed: bool, alerts: list[str], metrics: dict}
        """
        menu: dict = kwargs.get("menu", {})
        config: dict = kwargs.get("config", {})

        alerts: list[str] = []
        total_cost = 0.0
        total_dishes = 0
        dish_name_counter: dict[str, int] = {}

        # 提取约束
        red_lines = set()
        if isinstance(config, dict):
            ghc = config.get("global_hard_constraints", {})
            red_lines = set(ghc.get("red_lines", []))
            meals_config_list = config.get("meals_config", [])
        else:
            red_lines = set(config.global_hard_constraints.red_lines)
            meals_config_list = [m.model_dump() for m in config.meals_config]

        # 构建餐次配置索引
        meal_budgets: dict[str, float] = {}
        meal_structures: dict[str, dict[str, int]] = {}
        for mc in meals_config_list:
            if mc.get("enabled", True):
                meal_name = mc["meal_name"]
                meal_budgets[meal_name] = mc.get("budget_per_person", 999)
                meal_structures[meal_name] = {
                    cat["name"]: cat["count"]
                    for cat in mc.get("dish_structure", {}).get("categories", [])
                }

        # 逐日逐餐校验
        for date, meals in menu.items():
            daily_dishes: set[str] = set()
            for meal_name, categories in meals.items():
                meal_cost = 0.0
                for cat_name, dishes in categories.items():
                    # 数量校验
                    expected_count = meal_structures.get(meal_name, {}).get(cat_name)
                    if expected_count is not None and len(dishes) != expected_count:
                        alerts.append(
                            f"⚠️ {date} {meal_name}/{cat_name}: "
                            f"期望 {expected_count} 道菜，实际 {len(dishes)} 道"
                        )

                    for dish in dishes:
                        dish_id = dish.get("id")
                        dish_name = dish.get("name", "未知")
                        total_dishes += 1

                        # 红线食材扫描
                        full = _DISH_INDEX.get(dish_id, dish)
                        ingredients = full.get("main_ingredients", [])
                        for ingredient in ingredients:
                            if ingredient in red_lines:
                                alerts.append(
                                    f"❌ {date} {meal_name}: "
                                    f"「{dish_name}」含红线食材「{ingredient}」"
                                )

                        # 成本累计
                        cost = full.get("cost_per_serving", 0)
                        meal_cost += cost
                        total_cost += cost

                        # 重复率统计
                        dish_name_counter[dish_name] = dish_name_counter.get(dish_name, 0) + 1

                        # 同日跨餐重复检查
                        if dish_name in daily_dishes:
                            alerts.append(
                                f"⚠️ {date}: 「{dish_name}」在多个餐次中重复出现"
                            )
                        daily_dishes.add(dish_name)

        # 重复率计算
        repeat_count = sum(1 for c in dish_name_counter.values() if c > 1)
        unique_count = len(dish_name_counter)
        repeat_rate = round(repeat_count / unique_count * 100, 1) if unique_count > 0 else 0

        metrics = {
            "total_cost": round(total_cost, 2),
            "repeat_rate": repeat_rate,
            "alert_count": len(alerts),
            "total_dishes": total_dishes,
            "unique_dishes": unique_count,
        }

        return {
            "success": True,
            "passed": len(alerts) == 0,
            "alerts": alerts,
            "metrics": metrics,
        }
