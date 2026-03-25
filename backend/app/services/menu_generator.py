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
import random
from collections import defaultdict
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


def pre_filter_candidate_dishes(
    all_dishes: list[Any],
    config: MenuPlanConfig,
    red_lines: list[str],
    excluded_dishes: list[str],
) -> list[Any]:
    """
    按菜品结构从全量菜品库中预筛选出 50~100 道候选菜品，大幅降低提示词长度。

    为什么需要预筛选：
    全部 700+ 道菜的配料详情送入 LLM 会导致上下文过长（~15K tokens），
    LLM 容易忽略部分规则约束，且生成速度慢。预筛选后仅保留 50~100 道，
    token 消耗降低 ~80% 以上。

    筛选策略：
    1. 排除红线食材、已排过的菜品
    2. 按 applicable_meals 匹配当天启用的餐次
    3. 按 dish_structure.categories 统计每个分类的需求量，取 4 倍候选
    4. 口味打散：从不同 flavor 中均匀选取，避免候选集口味单一

    Args:
        all_dishes:      数据库全量菜品 ORM 对象列表
        config:          当天排餐配置
        red_lines:       全局红线食材列表
        excluded_dishes: 已在前几天排过的菜品名称列表（跨天去重）

    Returns:
        筛选后的菜品 ORM 对象列表（50~100 道）
    """
    red_lines_set = set(red_lines)
    excluded_set = set(excluded_dishes)

    # 统计当天各分类需求总量
    enabled_meals = [m for m in config.meals_config if m.enabled]
    enabled_meal_names = {m.meal_name for m in enabled_meals}
    category_demand: dict[str, int] = defaultdict(int)
    for meal in enabled_meals:
        for cat in meal.dish_structure.categories:
            category_demand[cat.name] += cat.count

    # 第一轮：规则过滤
    filtered: list[Any] = []
    for dish in all_dishes:
        # 红线检查
        ingredients = (
            [ing.get("name", "") for ing in dish.ingredients_quantified]
            if isinstance(dish.ingredients_quantified, list)
            else []
        )
        if any(ing in red_lines_set for ing in ingredients):
            continue
        # 跨天去重
        if dish.name in excluded_set:
            continue
        # 餐次匹配
        applicable = dish.applicable_meals if isinstance(dish.applicable_meals, list) else []
        if applicable and not enabled_meal_names.intersection(applicable):
            continue
        filtered.append(dish)

    # 第二轮：按分类分桶 + 口味多样化取样
    by_category: dict[str, list[Any]] = defaultdict(list)
    for dish in filtered:
        cat = dish.category or "其他"
        by_category[cat].append(dish)

    candidates: list[Any] = []
    selected_ids: set[int] = set()
    MULTIPLIER = 4  # 每个分类取需求量的 4 倍候选

    # 小品类总数本就不多，全量保留不做采样
    FULL_INCLUDE_CATEGORIES: set[str] = {
        "主食", "面点类", "汤羹类", "牛奶饮品类", "甜点糕点类", 
        "水果类", "咸菜腌菜类", "蛋类", "豆制品类", "菌菇类", "凉菜"
    }

    for cat_name, demand_count in category_demand.items():
        pool = by_category.get(cat_name, [])

        # 小品类全量保留
        if cat_name in FULL_INCLUDE_CATEGORIES:
            for dish in pool:
                if dish.id not in selected_ids:
                    candidates.append(dish)
                    selected_ids.add(dish.id)
            continue

        target = max(demand_count * MULTIPLIER, 8)  # 至少 8 道

        if len(pool) <= target:
            for dish in pool:
                if dish.id not in selected_ids:
                    candidates.append(dish)
                    selected_ids.add(dish.id)
        else:
            # 口味打散：按 flavor 分组后轮询选取
            by_flavor: dict[str, list[Any]] = defaultdict(list)
            for dish in pool:
                by_flavor[dish.flavor or "其他"].append(dish)
            # 每个口味组内随机打散
            for flavor_dishes in by_flavor.values():
                random.shuffle(flavor_dishes)

            # 轮询选取直到凑满 target
            flavor_keys = list(by_flavor.keys())
            random.shuffle(flavor_keys)
            idx_map = {k: 0 for k in flavor_keys}
            count = 0
            while count < target:
                picked_this_round = False
                for fk in flavor_keys:
                    if idx_map[fk] < len(by_flavor[fk]):
                        dish = by_flavor[fk][idx_map[fk]]
                        idx_map[fk] += 1
                        if dish.id not in selected_ids:
                            candidates.append(dish)
                            selected_ids.add(dish.id)
                            count += 1
                            picked_this_round = True
                        if count >= target:
                            break
                if not picked_this_round:
                    break

    # 补充 category_demand 中未出现的分类（如分类名与菜品 category 不完全对齐的情况）
    for cat_name, dishes in by_category.items():
        if cat_name not in category_demand:
            sample_size = min(len(dishes), 6)
            for dish in random.sample(dishes, sample_size):
                if dish.id not in selected_ids:
                    candidates.append(dish)
                    selected_ids.add(dish.id)

    logger.info(
        f"Pre-filter: {len(all_dishes)} -> {len(candidates)} candidates "
        f"(demand={dict(category_demand)}, excluded={len(excluded_set)})"
    )
    return candidates


def build_filtered_dishes_text(red_lines: list[str], excluded_dishes: list[str], all_dishes: list[Any]) -> str:
    """
    根据红线食材和排重列表动态构建菜品库文本。

    注意：此函数现在接收的 all_dishes 为预筛选后的候选菜品（50~100 道），
    而非全量 700+ 道菜，因此提示词长度大幅缩短。
    配料分类克数信息保留，供 LLM 做灶别营养凑配。
    """
    red_lines_set = set(red_lines)
    excluded_set = set(excluded_dishes)
    dishes_by_category: dict[str, list[str]] = {}
    
    for d in all_dishes:
        # 提取 ORM 对象或 dict 的属性
        ingredients_q = d.ingredients_quantified if hasattr(d, 'ingredients_quantified') else (d.get('ingredients_quantified', []) if isinstance(d, dict) else [])
        dish_name = d.name if hasattr(d, 'name') else (d.get('name', '') if isinstance(d, dict) else '')
        dish_id = d.id if hasattr(d, 'id') else (d.get('id', 0) if isinstance(d, dict) else 0)
        dish_cost = d.cost_per_serving if hasattr(d, 'cost_per_serving') else (d.get('cost_per_serving', 0) if isinstance(d, dict) else 0)
        dish_flavor = d.flavor if hasattr(d, 'flavor') else (d.get('flavor', '') if isinstance(d, dict) else '')
        dish_category = d.category if hasattr(d, 'category') else (d.get('category', '其他') if isinstance(d, dict) else '其他')

        ingredients = [ing.get("name", "") for ing in ingredients_q] if isinstance(ingredients_q, list) else []
        if any(ing in red_lines_set for ing in ingredients):
            continue
        if dish_name in excluded_set:
            continue
            
        cat = dish_category or "其他"
        if cat not in dishes_by_category:
            dishes_by_category[cat] = []

        # 精简配料展示：只保留分类和克数（LLM 需要据此凑配灶别标准）
        compact_ingredients = []
        for ing in (ingredients_q if isinstance(ingredients_q, list) else []):
            if isinstance(ing, dict):
                ing_cat = ing.get("category") or ing.get("name", "")
                ing_amt = ing.get("amount_g") or ing.get("amount") or ing.get("value") or 0
                if ing_cat and ing_amt:
                    compact_ingredients.append(f"{ing_cat}:{ing_amt}g")

        ingredients_str = ",".join(compact_ingredients) if compact_ingredients else "无"
        dishes_by_category[cat].append(
            f'{dish_name}(id:{dish_id}, 配料:[{ingredients_str}], 口味:{dish_flavor}, 成本:¥{dish_cost})'
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
        cats = ", ".join([f"{c.name}(需选{c.count}道)" for c in meal.dish_structure.categories])
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
2. 同一天不同餐次之间菜品不得重复（主食类除外，午餐和晚餐可使用相同主食）。
3. 单人餐标不得超出预算。
4. 【最重要指标】你必须预估该日所有选中菜品的配料（ingredients_quantified）乘以总就餐人数后的总和，尽可能使其逼近甚至等同该「{config.context_overview.kitchen_class}」的官方营养配额标准（肉类、蔬菜类等大类）。
5. 「已排过的菜品」绝对不能选。
6. 尽量优先搭配不同口味（酸/甜/咸/辣/清淡），保证丰富度。

## 输出格式（严格 JSON，分类名不要带数量后缀）
⚠️ 分类名只使用纯名称如"主食"、"大荤"、"素菜"，绝对不要写成"主食×1"或"主食(需选1道)"。
示例：{{"date": "{date}", "meals": {{"午餐": {{"大荤": [{{"id": 163, "name": "红烧肉圆"}}], "素菜": [{{"id": 507, "name": "清炒藕片"}}]}}}}}}"""

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
        candidate_dishes: list[Any] | None = kwargs.get("candidate_dishes", None)
        standard_quota_str: str = kwargs.get("standard_quota_str", "{}")

        # 如果编排器未传入预筛选候选，则自行查库（兼容旧接口）
        if candidate_dishes is None:
            from ..database import AsyncSessionLocal
            from sqlalchemy import select
            from ..models.dish import Dish
            from ..models.standard_quota import StandardQuota
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Dish))
                all_dishes_raw = result.scalars().all()
                
                kitchen_class = config.context_overview.kitchen_class
                sq_res = await session.execute(select(StandardQuota).where(StandardQuota.class_type == kitchen_class))
                sq = sq_res.scalars().first()
                standard_quota_str = json.dumps(sq.quotas, ensure_ascii=False) if sq else "{}"

            red_lines = config.global_hard_constraints.red_lines or []
            candidate_dishes = pre_filter_candidate_dishes(
                all_dishes=all_dishes_raw,
                config=config,
                red_lines=red_lines,
                excluded_dishes=excluded_dishes,
            )

        system_prompt = build_single_day_prompt(
            config=config,
            date=date,
            all_dishes=candidate_dishes,
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
        candidate_dishes: list[Any] | None = kwargs.get("candidate_dishes", None)
        standard_quota_str: str = kwargs.get("standard_quota_str", "{}")

        # 如果编排器未传入预筛选候选，则自行查库（兼容旧接口）
        if candidate_dishes is None:
            from ..database import AsyncSessionLocal
            from sqlalchemy import select
            from ..models.dish import Dish
            from ..models.standard_quota import StandardQuota
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Dish))
                all_dishes_raw = result.scalars().all()
                
                kitchen_class = config.context_overview.kitchen_class
                sq_res = await session.execute(select(StandardQuota).where(StandardQuota.class_type == kitchen_class))
                sq = sq_res.scalars().first()
                standard_quota_str = json.dumps(sq.quotas, ensure_ascii=False) if sq else "{}"

            red_lines = config.global_hard_constraints.red_lines or []
            candidate_dishes = pre_filter_candidate_dishes(
                all_dishes=all_dishes_raw,
                config=config,
                red_lines=red_lines,
                excluded_dishes=excluded_dishes,
            )

        system_prompt = build_single_day_prompt(
            config=config,
            date=date,
            all_dishes=candidate_dishes,
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
