"""
走云智能排菜系统 — 菜单生成智能体

职责：根据结构化排菜需求 + 菜品库，生成菜单。
支持两种模式：
  1. execute()：非流式，生成完整一周菜单（兼容旧接口）
  2. execute_single_day()：非流式，生成单天菜单（供编排器按天并行调用）

为减少 token 消耗，LLM 只输出 {id, name}，由数据补全智能体补全完整属性。
"""
import json
import logging
from typing import Any, AsyncGenerator

from pydantic import BaseModel
from openai import AsyncOpenAI
import httpx

from ..config import LLM_API_URL, LLM_API_KEY, LLM_MODEL
from ..schemas.chat_schema import MenuPlanConfig
from .base_agent import BaseAgent
from .utils import extract_json, extract_partial_json

logger = logging.getLogger(__name__)

class DishItem(BaseModel):
    id: int
    name: str

class DayMenuModel(BaseModel):
    date: str
    meals: dict[str, dict[str, list[DishItem]]]


_client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_API_URL,
    timeout=httpx.Timeout(120.0, connect=10.0),
)


def build_filtered_dishes_text(red_lines: list[str], excluded_dishes: list[str], all_dishes: list[Any]) -> str:
    """根据红线食材和排重列表动态构建菜品库文本"""
    red_lines_set = set(red_lines)
    excluded_set = set(excluded_dishes)
    dishes_by_category: dict[str, list[str]] = {}
    
    for d in all_dishes:
        ingredients = [ing.get("name", "") for ing in d.ingredients_quantified] if isinstance(d.ingredients_quantified, list) else []
        if any(ing in red_lines_set for ing in ingredients):
            continue
        if d.name in excluded_set:
            continue
            
        cat = d.category or "其他"
        if cat not in dishes_by_category:
            dishes_by_category[cat] = []
        tags_str = ",".join(d.tags) if isinstance(d.tags, list) else ""
        dishes_by_category[cat].append(
            f'{d.name}(id:{d.id}, 配料:{d.ingredients_quantified}, 成本:¥{d.cost_per_serving}, 标签:[{tags_str}])'
        )
        
    parts = []
    for cat, items in dishes_by_category.items():
        parts.append(f"【{cat}】\n" + "\n".join(f"  - {item}" for item in items))
    return "\n".join(parts)


def build_single_day_prompt(
    config: MenuPlanConfig,
    date: str,
    all_dishes: list[Any],
    intent_summary: str = "",
    excluded_dishes: list[str] | None = None,
    retry_alerts: list[str] | None = None,
    locked_meals: dict | None = None,
    standard_quota_str: str = "{}",
) -> str:
    """
    构建单天菜单生成 Prompt。

    为什么按天而非按周生成：
    单天 prompt 更短，LLM 输出更短，token 消耗降低约 80%，
    且多天可并行调用，总耗时从 ~60s 降至 ~15s。

    Args:
        config:           完整排餐配置
        date:             目标日期（YYYY-MM-DD）
        intent_summary:   用户意图摘要
        excluded_dishes:  已在其他天出现的菜品名称列表（用于跨天去重）
        retry_alerts:     上一轮校验的不合格项（重试时携带，让 LLM 有针对性修正）

    Returns:
        System Prompt 字符串
    """
    enabled_meals = [m for m in config.meals_config if m.enabled]

    from datetime import date as date_cls
    target_date = date_cls.fromisoformat(date)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = weekdays[target_date.weekday()]

    active_health = [
        h.model_dump() for h in config.global_hard_constraints.health_conditions if h.enabled
    ]
    active_dietary = [
        d.model_dump() for d in config.global_hard_constraints.dietary_restrictions if d.enabled
    ]

    meals_desc = []
    for meal in enabled_meals:
        cats = ", ".join([f"{c.name}×{c.count}" for c in meal.dish_structure.categories])
        meals_desc.append(
            f"  - {meal.meal_name}: {meal.diners_count}人, 餐标¥{meal.budget_per_person}/人, "
            f"分类=[{cats}], 主食细类=[{','.join(meal.staple_types)}], 汤品描述=[{meal.soup_requirements.description}], "
            f"口味偏好=[{meal.flavor_preferences}], "
            f"必用食材={meal.meal_specific_constraints.required_ingredients}, "
            f"必排菜品={meal.meal_specific_constraints.mandatory_dishes}"
        )

    excluded_text = ""
    if excluded_dishes:
        excluded_text = (
            f"\n## 已排过的菜品（本天绝对禁止选用以下任何菜品）\n"
            f"{', '.join(excluded_dishes)}\n"
            f"⚠️ 上述菜品已在其他天使用过，你必须从可选菜品库中选择未出现过的菜品。"
        )

    retry_text = ""
    if retry_alerts:
        retry_text = (
            f"\n## ⚠️ 上一轮校验不合格项（必须针对性修正）\n"
            + "\n".join(f"  - {a}" for a in retry_alerts)
        )

    locked_text = ""
    if locked_meals:
        locked_text = (
            f"\n## 锁定餐次（不可修改，必须原样输出）\n"
            f"重要指引：用户仅要求修改本天的部分餐次。对于以下锁定的餐次及其菜品，你在最终输出 JSON 时，【必须原封不动地原样保留返回】，你只需针对那些未被锁定的餐次进行重新生成选菜。\n"
            f"{json.dumps(locked_meals, ensure_ascii=False)}\n"
        )

    red_lines_list = config.global_hard_constraints.red_lines if config.global_hard_constraints.red_lines else []
    filtered_dishes_text = build_filtered_dishes_text(red_lines_list, excluded_dishes or [], all_dishes)

    system_prompt = f"""你是智能排菜系统的菜单生成智能体（武警总队版）。为 {date}（{weekday_str}）生成单天菜单。

## 排餐环境
- 灶别标准: {config.context_overview.kitchen_class} | 城市: {config.context_overview.city}
- 该灶别配给标准（克/人/天）: {standard_quota_str} (⚠️ 请尽力让今日所有菜品所含配料的人均累计消耗量凑齐满足此标准)
- 全局意图与偏好: {intent_summary or '按默认配置排菜'}
  (⚠️ 核心原则：如果意图中提到了限定时间的偏好，如“{weekday_str}清淡”，你必须在当前生成的这份菜单中严苛执行该要求！)

## 餐次配置
{chr(10).join(meals_desc)}

## 全局红线（绝对禁止）
{red_lines_list if red_lines_list else '无'}

## 饮食禁忌与重排反馈
{excluded_text}
{retry_text}
{locked_text}
## 可选菜品库（已为您过滤掉红线和排重菜品，括号内提供了配料的克数详情）
{filtered_dishes_text}

## 排菜规则（必须严格遵守）
1. 严格按各餐次分类结构的数量选菜，不得多选或少选。
2. 同一天不同餐次之间菜品不得重复。
3. 单人餐标不得超出预算。
4. 【最重要指标】你必须预估该日所有选中菜品的配料（ingredients_quantified）乘以总就餐人数后的总和，尽可能使其逼近甚至等同该「{config.context_overview.kitchen_class}」的官方营养配额标准（肉类、蔬菜类等大类）。
5. 「已排过的菜品」绝对不能选。
6. 尽量优先搭配不同口味（酸/甜/咸/辣/清淡），保证丰富度。

## 输出格式（严格 JSON）
{{"date": "{date}", "meals": {{"餐次名": {{"分类名": [{{"id": 菜品ID, "name": "菜品名"}}]}}}}}}"""

    # 调试功能：将最后生成的 Prompt 写入本地文件，方便核对实际约束
    import os
    import datetime
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "prompts")
    os.makedirs(debug_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    retry_suffix = "_retry" if retry_alerts else ""
    with open(os.path.join(debug_dir, f"prompt_{date}_{timestamp}{retry_suffix}.txt"), "w", encoding="utf-8") as f:
        f.write(system_prompt)
        
    return system_prompt


class MenuGeneratorAgent(BaseAgent):
    """菜单生成智能体"""

    agent_id = "menu-generator"
    agent_name = "Menu Generator / 菜单生成智能体"
    agent_description = "根据结构化排菜需求，从菜品库中选菜组装菜单，严格遵守分类数量、预算、红线等约束规则"
    agent_type = "llm"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        非流式执行：生成完整一周菜单（供单独 API 调用）。

        Args:
            config:         MenuPlanConfig 对象
            user_message:   用户原始消息
            intent_summary: 意图解析摘要

        Returns:
            {success: bool, menu: dict, summary: str}
        """
        config: MenuPlanConfig = kwargs["config"]
        user_message: str = kwargs.get("user_message", "帮我排下周菜单")
        intent_summary: str = kwargs.get("intent_summary", "")

        # 获取需要生成的日期列表
        from datetime import date as date_cls, timedelta
        start = date_cls.fromisoformat(config.context_overview.schedule.start_date)
        end = date_cls.fromisoformat(config.context_overview.schedule.end_date)
        dates = []
        cur = start
        while cur <= end:
            dates.append(cur.isoformat())
            cur += timedelta(days=1)

        # 顺序生成（非流式模式保持简单）
        full_menu: dict = {}
        all_dish_names: list[str] = []
        for d in dates:
            day_result = await self.execute_single_day(
                config=config,
                date=d,
                intent_summary=intent_summary,
                excluded_dishes=all_dish_names.copy(),
            )
            if day_result.get("success") and day_result.get("day_menu"):
                full_menu[d] = day_result["day_menu"]
                all_dish_names.extend(day_result.get("dish_names", []))

        if full_menu:
            return {"success": True, "menu": full_menu, "summary": "菜单已生成"}
        return {"success": False, "error": "所有日期菜单生成失败"}

    async def execute_single_day(self, **kwargs: Any) -> dict[str, Any]:
        """
        生成单天菜单（非流式）。

        Args:
            config:          MenuPlanConfig 对象
            date:            目标日期字符串 YYYY-MM-DD
            intent_summary:  意图摘要
            excluded_dishes: 已排过的菜品名列表（跨天去重）
            retry_alerts:    上一轮约束告警列表（重试时携带）
            locked_meals:    指定不需要修改的餐次数据，字典格式

        Returns:
            {
                success:    bool,
                date:       str,
                day_menu:   {meal_name: {category: [{id, name}]}},
                dish_names: list[str],  本天所有选中菜品名
            }
        """
        config: MenuPlanConfig = kwargs["config"]
        date: str = kwargs["date"]
        intent_summary: str = kwargs.get("intent_summary", "")
        excluded_dishes: list[str] = kwargs.get("excluded_dishes", [])
        retry_alerts: list[str] = kwargs.get("retry_alerts", [])
        locked_meals: dict | None = kwargs.get("locked_meals", None)

        from ..database import AsyncSessionLocal
        from sqlalchemy import select
        from ..models.dish import Dish
        from ..models.standard_quota import StandardQuota
        import json
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Dish))
            all_dishes = result.scalars().all()
            
            kitchen_class = config.context_overview.kitchen_class
            sq_res = await session.execute(select(StandardQuota).where(StandardQuota.class_type == kitchen_class))
            sq = sq_res.scalars().first()
            standard_quota_str = json.dumps(sq.quotas, ensure_ascii=False) if sq else "{}"

        system_prompt = build_single_day_prompt(
            config=config,
            date=date,
            all_dishes=all_dishes,
            intent_summary=intent_summary,
            excluded_dishes=excluded_dishes,
            retry_alerts=retry_alerts,
            locked_meals=locked_meals,
            standard_quota_str=standard_quota_str,
        )

        try:
            response = await _client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请为 {date} 生成菜单"},
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            
            # 使用 Pydantic 校验结果，确保结构安全
            try:
                validated_model = DayMenuModel.model_validate_json(raw)
                parsed = validated_model.model_dump()
            except Exception as valid_e:
                # 兼容旧的回退提取逻辑
                logger.warning(f"Pydantic 校验失败，尝试退化提取: {valid_e}")
                parsed = extract_json(raw)

            if parsed and "meals" in parsed:
                day_menu = parsed["meals"]
                # 提取所有菜品名，供其他天去重使用
                dish_names = [
                    dish.get("name", "")
                    for categories in day_menu.values()
                    for dishes in categories.values()
                    for dish in dishes
                ]
                return {
                    "success": True,
                    "date": date,
                    "day_menu": day_menu,
                    "dish_names": dish_names,
                }
            else:
                logger.warning(f"[menu-generator] {date} invalid JSON. First 200: {raw[:200]}")
                return {"success": False, "date": date, "error": "AI 返回格式异常或未通过结构校验", "raw": raw[:300]}

        except Exception as e:
            logger.exception(f"[menu-generator] {date} generation failed")
            return {"success": False, "date": date, "error": str(e)}

    async def execute_stream(self, **kwargs: Any) -> AsyncGenerator[tuple[str, int], None]:
        """
        流式执行单天菜单生成（供编排器实时推进度使用）。

        Yields:
            (累积的原始文本, 当前 token 计数)
        """
        config: MenuPlanConfig = kwargs["config"]
        date: str = kwargs["date"]
        intent_summary: str = kwargs.get("intent_summary", "")
        excluded_dishes: list[str] = kwargs.get("excluded_dishes", [])
        retry_alerts: list[str] = kwargs.get("retry_alerts", [])
        locked_meals: dict | None = kwargs.get("locked_meals", None)

        from ..database import AsyncSessionLocal
        from sqlalchemy import select
        from ..models.dish import Dish
        from ..models.standard_quota import StandardQuota
        import json
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Dish))
            all_dishes = result.scalars().all()
            
            kitchen_class = config.context_overview.kitchen_class
            sq_res = await session.execute(select(StandardQuota).where(StandardQuota.class_type == kitchen_class))
            sq = sq_res.scalars().first()
            standard_quota_str = json.dumps(sq.quotas, ensure_ascii=False) if sq else "{}"

        system_prompt = build_single_day_prompt(
            config=config,
            date=date,
            all_dishes=all_dishes,
            intent_summary=intent_summary,
            excluded_dishes=excluded_dishes,
            retry_alerts=retry_alerts,
            locked_meals=locked_meals,
            standard_quota_str=standard_quota_str,
        )

        stream = await _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请为 {date} 生成菜单"},
            ],
            temperature=0.7,
            max_tokens=4000,
            stream=True,
            response_format={"type": "json_object"},
        )

        raw_content = ""
        token_count = 0
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                raw_content += delta.content
                token_count += 1
                yield raw_content, token_count
