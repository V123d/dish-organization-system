"""
走云智能排菜系统 — 多智能体编排器 (v2)

重写变更：
- 按天折中并行：日期列表分为 2-3 天一组，组内 asyncio.gather() 并行，组间顺序执行
  （组间顺序是为了将前几天已选菜品传递到后续天做跨天去重）
- 逐天流式输出：每天菜单生成后立即发送 menu_update 事件填充日历看板
- 约束校验具体告警：通过 constraint_alert SSE 事件输出每条不合格项
- 重试反馈：将约束告警回传给 LLM，发送 menu_remove 事件清空旧菜品，再重新生成
- SSE 事件兼容：保留 thinking / content / menu_result / error 事件类型
"""
import asyncio
import logging
from datetime import date as date_cls, timedelta
from typing import AsyncGenerator

from ..schemas.chat_schema import MenuPlanConfig
from .menu_generator import DayMenuModel, pre_filter_candidate_dishes
from .base_agent import AgentRegistry
from .constraint_checker import _check_menu, _check_daily_nutrition
from .data_enrichment import _enrich_menu_data
from .utils import sse, extract_json, extract_partial_json

logger = logging.getLogger(__name__)

MAX_RETRIES = 2       # 单天校验不通过时的最大重排次数
GROUP_SIZE = 1        # 每组并行的天数 (改为1消除排菜盲区)

# ── 极简状态图实现 ──
class StateGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.entry_point = None
        
    def add_node(self, name: str, func: callable):
        self.nodes[name] = func
        
    def add_edge(self, from_node: str, to_node: str):
        self.edges[from_node] = to_node
        
    def add_conditional_edges(self, from_node: str, func: callable):
        self.edges[from_node] = func
        
    def set_entry_point(self, name: str):
        self.entry_point = name
        
    async def run(self, state: dict) -> AsyncGenerator[str, None]:
        current_node = self.entry_point
        while current_node != "end":
            node_func = self.nodes[current_node]
            async for sse_event in node_func(state):
                yield sse_event
                
            edge = self.edges.get(current_node)
            if callable(edge):
                current_node = edge(state)
            else:
                current_node = edge

# ── 图节点函数 ──
async def node_generate(state: dict) -> AsyncGenerator[str, None]:
    date_str = state["date"]
    attempt = state.get("attempt", 0)
    menu_agent = state["menu_agent"]
    
    yield sse("thinking", {"step": {
        "label": f"生成菜单 ({date_str})",
        "status": "running",
        "detail": f"正在生成第 {attempt + 1} 次尝试..." if attempt > 0 else "正在生成菜单...",
    }})
    
    stream_gen = menu_agent.execute_stream(
        config=state["config"],
        date=date_str,
        intent_summary=state["intent_summary"],
        excluded_dishes=state["excluded_dishes"],
        retry_alerts=state.get("retry_alerts", []),
        locked_meals=state.get("locked_meals"),
        candidate_dishes=state.get("candidate_dishes"),
        standard_quota_str=state.get("standard_quota_str", "{}"),
    )
    
    raw_content = ""
    # 我们用 throttling 防止 partial JSON 发送过快挤爆前端
    update_tick = 0
    async for chunk_text, token_count in stream_gen:
        raw_content = chunk_text
        update_tick += 1
        if update_tick % 10 == 0:  # 降低频率
            partial_obj = extract_partial_json(raw_content)
            if partial_obj and "meals" in partial_obj:
                yield sse("menu_partial_update", {"date": date_str, "meals": partial_obj["meals"]})
                
    # 完成生成后验证
    try:
        validated = DayMenuModel.model_validate_json(raw_content)
        day_menu = validated.model_dump()["meals"]
    except Exception as e:
        logger.warning(f"Generator partial JSON parsing fallback on {date_str}: {e}")
        parsed_fallback = extract_json(raw_content) or extract_partial_json(raw_content)
        day_menu = parsed_fallback.get("meals") if parsed_fallback else None
        
    if day_menu:
        state["day_menu"] = day_menu
        yield sse("menu_update", {"date": date_str, "meals": day_menu})
        yield sse("thinking", {"step": {
            "label": f"生成菜单 ({date_str})",
            "status": "done",
            "detail": f"{date_str} 菜单生成成功 ✓",
        }})
    else:
        state["day_menu"] = None
        state["error"] = "未能正确格式化菜单数据"

async def node_check(state: dict) -> AsyncGenerator[str, None]:
    """约束校验节点：结构性校验 + 逐天营养达标校验"""
    date_str = state["date"]
    day_menu = state.get("day_menu")
    if not day_menu:
        state["passed"] = False
        return
        
    check_result = await _check_menu({date_str: day_menu}, state["config_dict"])
    day_alerts = check_result.get("alerts", [])

    # 逐天营养达标校验（仅计算展示，不影响通过判定）
    # 为什么不作为重试约束：当前数据库配料分类标注尚不完整，
    # 某些菜品明明含某配料但未标注，会导致误判为不达标。
    nutrition_result = await _check_daily_nutrition(
        day_menu=day_menu,
        config_dict=state["config_dict"],
        date_str=date_str,
    )

    # 推送每日营养达标数据到前端（仅展示）
    quota_compliance = nutrition_result.get("quota_compliance", [])
    if quota_compliance:
        yield sse("daily_quota_update", {
            "date": date_str,
            "quota_compliance": quota_compliance,
        })
    
    if day_alerts:
        yield sse("constraint_alert", {
            "date": date_str,
            "alerts": day_alerts,
            "attempt": state.get("attempt", 0) + 1,
        })
        
    # 将结构化告警转为 LLM 可读字符串，便于重试时针对性修正
    readable_alerts = [
        f"[{a.get('type', '未知')}] "
        f"{a.get('meal_name', '')}"
        f"{'/' + a.get('category', '') if a.get('category') else ''}"
        f"{'/' + a.get('dish_name', '') if a.get('dish_name') else ''}"
        f": {a.get('detail', '未知问题')}"
        for a in day_alerts
    ]
    alerts_summary = '；'.join(readable_alerts) if readable_alerts else ''

    if check_result.get("passed"):
        state["passed"] = True
        yield sse("thinking", {"step": {
            "label": "约束校验",
            "status": "done",
            "detail": f"{date_str} 所有约束验证通过 ✓",
        }})
    else:
        state["passed"] = False
        state["retry_alerts"] = readable_alerts
        # 若需要重试，在边(edge)逻辑中自增并触发 remove
        if state.get("attempt", 0) < MAX_RETRIES:
            yield sse("thinking", {"step": {
                "label": "约束校验",
                "status": "error",
                "detail": f"{date_str} 发现 {len(day_alerts)} 项问题: {alerts_summary}，进入重试",
            }})
            yield sse("menu_remove", {"date": date_str})
        else:
            yield sse("thinking", {"step": {
                "label": "约束校验",
                "status": "done",
                "detail": f"{date_str} 多次尝试仍有约束未满足: {alerts_summary}",
            }})

async def node_enrich(state: dict) -> AsyncGenerator[str, None]:
    date_str = state["date"]
    day_menu = state.get("day_menu")
    if day_menu:
        yield sse("thinking", {"step": {
            "label": f"数据补全 ({date_str})",
            "status": "running",
            "detail": "正在获取完整菜品工艺与排菜数据",
        }})
        enriched_day = await _enrich_menu_data({date_str: day_menu})
        state["day_menu"] = enriched_day.get(date_str, day_menu)
        # 再推一次带完整 detail 的 update
        yield sse("menu_update", {"date": date_str, "meals": state["day_menu"]})
        yield sse("thinking", {"step": {
            "label": f"数据补全 ({date_str})/食材成本计算",
            "status": "done",
            "detail": f"{date_str} 数据补全与成本计算完成 ✓",
        }})

def check_edge(state: dict) -> str:
    if state.get("day_menu") is None:
        return "end" # 发生致命错误停止
    if state.get("passed"):
        return "enrich"
    if state.get("attempt", 0) < MAX_RETRIES:
        state["attempt"] = state.get("attempt", 0) + 1
        return "generate"
    return "enrich"


def build_day_graph() -> StateGraph:
    graph = StateGraph()
    graph.add_node("generate", node_generate)
    graph.add_node("check", node_check)
    graph.add_node("enrich", node_enrich)
    
    graph.set_entry_point("generate")
    graph.add_edge("generate", "check")
    graph.add_conditional_edges("check", check_edge)
    graph.add_edge("enrich", "end")
    return graph


# ── 编排入口 ──
async def orchestrate_menu_stream(
    user_message: str,
    config_data: MenuPlanConfig,
    current_menu_data: dict | None = None,
    history: list[dict] | None = None
) -> AsyncGenerator[str, None]:
    
    intent_agent = AgentRegistry.get("intent-parser")
    menu_agent = AgentRegistry.get("menu-generator")
    
    if not all([intent_agent, menu_agent]):
        yield sse("error", {"message": "智能体未注册完备"})
        return

    config_json = config_data.model_dump_json(indent=None)
    config_dict = config_data.model_dump()
    current_menu_json = ""
    if current_menu_data:
        import json
        current_menu_json = json.dumps(current_menu_data, ensure_ascii=False)

    yield sse("thinking", {"step": {"label": "意图解析", "status": "running", "detail": "理解您的排餐诉求..."}})

    intent_result = await intent_agent.run(
        user_message=user_message, 
        config_json=config_json,
        current_menu_json=current_menu_json,
        history=history or []
    )
    include_weekends = False
    regenerate_targets = []

    if intent_result.get("success"):
        parsed_intent = intent_result.get("parsed_intent", {})
        intent_summary = parsed_intent.get("summary", user_message)
        include_weekends = parsed_intent.get("include_weekends", False)

        daily_overrides = parsed_intent.get("daily_overrides", {})
        meal_overrides = parsed_intent.get("meal_overrides", [])
        regenerate_targets = parsed_intent.get("regenerate_targets", [])

        # ── 将意图解析的具体偏好注入到 intent_summary，确保 Prompt 包含明确指令 ──
        prefs = parsed_intent.get("global_preferences", [])
        if prefs:
            intent_summary += f"；全局偏好: {', '.join(prefs)}"

        # ── 应用预算覆盖：用户明确提出新预算时，运行时修改 config ──
        budget_override = parsed_intent.get("budget_override")
        if budget_override is not None:
            try:
                new_budget = float(budget_override)
                for mc in config_data.meals_config:
                    mc.budget_per_person = new_budget
                # 重新序列化以反映修改
                config_dict = config_data.model_dump()
                logger.info(f"Budget overridden to ¥{new_budget}/人 by user intent")
            except (ValueError, TypeError):
                logger.warning(f"Invalid budget_override value: {budget_override}")

        yield sse("thinking", {"step": {"label": "意图解析", "status": "done", "detail": f"已解析：{intent_summary[:80]}"}})
    else:
        yield sse("thinking", {"step": {"label": "意图解析", "status": "error", "detail": "解析失败"}})
        intent_summary = user_message

    start = date_cls.fromisoformat(config_data.context_overview.schedule.start_date)
    end = date_cls.fromisoformat(config_data.context_overview.schedule.end_date)
    all_dates: list[str] = []
    cur = start
    while cur <= end:
        if include_weekends or cur.weekday() < 5:  # 跳周末 (除非意图解析明确包含)
            all_dates.append(cur.isoformat())
        cur += timedelta(days=1)
    if not all_dates:
        cur = start
        while cur <= end:
            all_dates.append(cur.isoformat())
            cur += timedelta(days=1)

    full_menu = {}
    
    is_partial_mode = current_menu_data is not None and intent_result.get("success") and len(regenerate_targets) > 0
    dates_to_generate = set()
    locked_meals_by_date = {}

    if is_partial_mode:
        for rt in regenerate_targets:
            rd = rt.get("date")
            if rd:
                dates_to_generate.add(rd)
        
        for d in dates_to_generate:
            meals_to_regen = [rt.get("meal_name") for rt in regenerate_targets if rt.get("date") == d]
            # 如果没有包含 '全部' 也没有包含空字符串，说明是精确指定了某些餐次
            if not any(not m or m == "全部" for m in meals_to_regen):
                if current_menu_data and d in current_menu_data:
                    day_data = current_menu_data[d]
                    # 记录并锁定那些不需要生成的餐次
                    locked_meals_by_date[d] = {
                        meal: data for meal, data in day_data.items()
                        if meal not in meals_to_regen
                    }
    else:
        dates_to_generate = set(all_dates)

    # ── 预先构建所有日期的 Config 和 Intent ──
    from copy import deepcopy
    from ..schemas.chat_schema import MenuPlanConfig
    
    daily_configs = {}
    daily_intents = {}
    
    for d in all_dates:
        target_date_obj = date_cls.fromisoformat(d)
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday_str = weekdays[target_date_obj.weekday()]

        # 1. 构建单天 intent
        day_intent_parts = []
        if intent_summary:
            day_intent_parts.append(intent_summary)
            
        daily_override = daily_overrides.get(weekday_str, {}) if intent_result.get("success") else {}
        if daily_override:
            if daily_override.get("flavor"):
                day_intent_parts.append(f"【{weekday_str}口味】: {daily_override['flavor']}")
            if daily_override.get("preferred_ingredients"):
                day_intent_parts.append(f"【{weekday_str}偏好食材】: {','.join(daily_override['preferred_ingredients'])}")
            if daily_override.get("avoid_ingredients"):
                day_intent_parts.append(f"【{weekday_str}避开食材】: {','.join(daily_override['avoid_ingredients'])}")
            if daily_override.get("special_requests"):
                day_intent_parts.append(f"【{weekday_str}特定要求】: {','.join(daily_override['special_requests'])}")

        daily_intents[d] = "；".join(day_intent_parts)

        # 2. 构建单天 config (Mutation)
        day_config_dict = deepcopy(config_dict)
        meal_overrides_list = meal_overrides if intent_result.get("success") else []
        for mo in meal_overrides_list:
            target = mo.get("target", "")
            if target.startswith(weekday_str) or "-" not in target:
                target_meal_name = target.split("-")[-1] if "-" in target else target
                
                for mc in day_config_dict.get("meals_config", []):
                    if mc.get("meal_name") == target_meal_name:
                        if mo.get("budget_override") is not None:
                            mc["budget_per_person"] = mo["budget_override"]
                            
                        cat_changes = mo.get("category_changes", {})
                        if cat_changes:
                            existing_cats = mc.get("dish_structure", {}).get("categories", [])
                            cat_map = {c["name"]: c["count"] for c in existing_cats}
                            for k, v in cat_changes.items():
                                cat_map[k] = v
                            
                            new_cats = [{"name": k, "count": v} for k, v in cat_map.items() if v > 0]
                            if "dish_structure" not in mc:
                                mc["dish_structure"] = {}
                            mc["dish_structure"]["categories"] = new_cats
                            
        day_config_obj = MenuPlanConfig(**day_config_dict)
        daily_configs[d] = {
            "config": day_config_obj,
            "config_dict": day_config_dict
        }

    selected_dishes_history = []  # tuple: (date_str, cat_name, dish_name)
    
    generate_dates = []
    
    # 将不需要生成的日期直接并入 full_menu，跳出 graph
    for d in all_dates:
        if is_partial_mode and d not in dates_to_generate:
            if current_menu_data and d in current_menu_data:
                full_menu[d] = current_menu_data[d]
                # 先通知前端不需要生成的餐次
                yield sse("menu_update", {"date": d, "meals": current_menu_data[d]})
                for cats in current_menu_data[d].values():
                    for cat_name, dishes in cats.items():
                        selected_dishes_history.extend([(d, cat_name, dish.get("name", "")) for dish in dishes])
        else:
            generate_dates.append(d)

    date_groups = [generate_dates[i: i + GROUP_SIZE] for i in range(0, len(generate_dates), GROUP_SIZE)]

    # 一次性预查全量菜品和灶别标准，避免每天重复查库
    from ..database import AsyncSessionLocal
    from sqlalchemy import select
    from ..models.dish import Dish
    from ..models.standard_quota import StandardQuota
    import json as json_mod

    async with AsyncSessionLocal() as session:
        all_dishes_result = await session.execute(select(Dish))
        all_dishes_cache = all_dishes_result.scalars().all()

        kitchen_class = config_data.context_overview.kitchen_class
        sq_res = await session.execute(select(StandardQuota).where(StandardQuota.class_type == kitchen_class))
        sq = sq_res.scalars().first()
        standard_quota_str_cache = json_mod.dumps(sq.quotas, ensure_ascii=False) if sq else "{}"

    logger.info(f"Pre-fetched {len(all_dishes_cache)} dishes and standard quota for '{kitchen_class}'")

    graph = build_day_graph()

    for group in date_groups:
        queue = asyncio.Queue()
        
        async def run_day_workflow(d: str):
            excluded_dishes = set()
            target_date_obj = date_cls.fromisoformat(d)
            for prev_d, cat, d_name in selected_dishes_history:
                prev_date_obj = date_cls.fromisoformat(prev_d)
                diff_days = abs((target_date_obj - prev_date_obj).days)
                if cat in {"汤"}:
                    continue
                elif cat == "素菜":
                    if diff_days <= 1:
                        excluded_dishes.add(d_name)
                else:
                    if diff_days <= 3:
                        excluded_dishes.add(d_name)

            # 预筛选候选菜品：从全量菜品库中按结构需求选出 50~100 道
            day_config = daily_configs[d]["config"]
            red_lines = day_config.global_hard_constraints.red_lines or []
            candidate_dishes = pre_filter_candidate_dishes(
                all_dishes=all_dishes_cache,
                config=day_config,
                red_lines=red_lines,
                excluded_dishes=list(excluded_dishes),
            )

            state = {
                "date": d,
                "config": day_config,
                "config_dict": daily_configs[d]["config_dict"],
                "intent_summary": daily_intents[d],
                "menu_agent": menu_agent,
                "excluded_dishes": list(excluded_dishes),
                "candidate_dishes": candidate_dishes,
                "standard_quota_str": standard_quota_str_cache,
                "attempt": 0,
                "locked_meals": locked_meals_by_date.get(d)
            }
            try:
                async for event in graph.run(state):
                    await queue.put(event)
                await queue.put({"_done": True, "date": d, "final_menu": state.get("day_menu")})
            except Exception as e:
                logger.error(f"Day graph err: {e}")
                await queue.put({"_done": True, "date": d, "final_menu": None})

        tasks = [asyncio.create_task(run_day_workflow(d)) for d in group]
        
        active_tasks = len(tasks)
        while active_tasks > 0:
            event = await queue.get()
            if isinstance(event, dict) and event.get("_done"):
                active_tasks -= 1
                if event.get("final_menu"):
                    d_str = event["date"]
                    day_m = event["final_menu"]
                    full_menu[d_str] = day_m
                    for cats in day_m.values():
                        for cat_name, dishes in cats.items():
                            selected_dishes_history.extend([(d_str, cat_name, dish.get("name", "")) for dish in dishes])
            elif isinstance(event, str):
                yield event
                # 对于部分关键动画加入极短延迟以免前端失帧
                if "menu_remove" in event:
                    await asyncio.sleep(0.3)
                    
    if not full_menu:
        yield sse("error", {"message": "由于网络或多次约束错误，菜单均未生成"})
        return

    try:
        # ── 全局校验 + 重试循环 ────────────────────────────────────────
        GLOBAL_RETRY_TYPES = {"CROSS_DAY_DUPLICATE", "HIGH_REPEAT_RATE"}
        MAX_GLOBAL_RETRIES = 2

        for global_attempt in range(MAX_GLOBAL_RETRIES + 1):
            daily_configs_dict_only = {k: v["config_dict"] for k,v in daily_configs.items()}
            final_check = await _check_menu(full_menu, config_dict, daily_configs_dict_only)
            global_alerts = [
                a for a in final_check.get("alerts", [])
                if a.get("type") in GLOBAL_RETRY_TYPES
            ]

            if not global_alerts or global_attempt >= MAX_GLOBAL_RETRIES:
                break

            dates_to_redo: set[str] = set()

            for a in global_alerts:
                if a.get("type") == "CROSS_DAY_DUPLICATE":
                    dates_to_redo.add(a.get("date", ""))

            if not dates_to_redo:
                sorted_dates = sorted(full_menu.keys())
                mid = len(sorted_dates) // 2
                dates_to_redo = set(sorted_dates[mid:])

            alert_summary = '；'.join(
                f"[{a.get('type','')}] {a.get('dish_name', '')}: {a.get('detail', '')}"
                for a in global_alerts[:5]
            )
            yield sse("thinking", {"step": {
                "label": "约束校验",
                "status": "error",
                "detail": f"全局第{global_attempt + 1}轮检查: {alert_summary}，重排 {len(dates_to_redo)} 天",
            }})

            kept_history = []
            for menu_d, day_m in full_menu.items():
                if menu_d not in dates_to_redo:
                    for cats in day_m.values():
                        for cat_name, dishes in cats.items():
                            kept_history.extend([(menu_d, cat_name, dish.get("name", "")) for dish in dishes])

            for d in dates_to_redo:
                full_menu.pop(d, None)
                yield sse("menu_remove", {"date": d})
            await asyncio.sleep(0.3)

            for d in sorted(dates_to_redo):
                retry_alerts_text = [
                    f"[{a.get('type','')}] {a.get('dish_name','')}: {a.get('detail','')}"
                    for a in global_alerts if a.get("date") == d or a.get("type") == "HIGH_REPEAT_RATE"
                ]

                yield sse("thinking", {"step": {
                    "label": "菜单生成",
                    "status": "running",
                    "detail": f"全局重排 {d}（第{global_attempt + 1}轮）",
                }})

                current_retry_excluded = set()
                target_date_obj = date_cls.fromisoformat(d)
                for prev_d, cat, d_name in kept_history:
                    prev_date_obj = date_cls.fromisoformat(prev_d)
                    diff_days = abs((target_date_obj - prev_date_obj).days)
                    if cat in {"汤"}:
                        continue
                    elif cat == "素菜":
                        if diff_days <= 1:
                            current_retry_excluded.add(d_name)
                    else:
                        if diff_days <= 3:
                            current_retry_excluded.add(d_name)

                # 全局重排也走预筛选
                retry_day_config = daily_configs[d]["config"]
                retry_red_lines = retry_day_config.global_hard_constraints.red_lines or []
                retry_candidates = pre_filter_candidate_dishes(
                    all_dishes=all_dishes_cache,
                    config=retry_day_config,
                    red_lines=retry_red_lines,
                    excluded_dishes=list(current_retry_excluded),
                )

                stream_gen = menu_agent.execute_stream(
                    config=retry_day_config,
                    date=d,
                    intent_summary=daily_intents[d],
                    excluded_dishes=list(current_retry_excluded),
                    retry_alerts=retry_alerts_text,
                    candidate_dishes=retry_candidates,
                    standard_quota_str=standard_quota_str_cache,
                )
                
                raw_content = ""
                update_tick = 0
                async for chunk_text, token_count in stream_gen:
                    raw_content = chunk_text
                    update_tick += 1
                    if update_tick % 10 == 0:
                        partial_obj = extract_partial_json(raw_content)
                        if partial_obj and "meals" in partial_obj:
                            yield sse("menu_partial_update", {"date": d, "meals": partial_obj["meals"]})
                
                day_menu = None
                try:
                    validated = DayMenuModel.model_validate_json(raw_content)
                    day_menu = validated.model_dump()["meals"]
                except Exception as e:
                    logger.warning(f"Retry parsing fallback on {d}: {e}")
                    parsed_fallback = extract_json(raw_content) or extract_partial_json(raw_content)
                    day_menu = parsed_fallback.get("meals") if parsed_fallback else None
                
                if day_menu:
                    enriched = await _enrich_menu_data({d: day_menu})
                    day_menu = enriched.get(d, day_menu)

                    full_menu[d] = day_menu
                    yield sse("menu_update", {"date": d, "meals": day_menu})

                    for cats in day_menu.values():
                        for cat_name, dishes in cats.items():
                            kept_history.extend([(d, cat_name, dish.get("name", "")) for dish in dishes])
                else:
                    yield sse("thinking", {"step": {
                        "label": "菜单重生成",
                        "status": "error",
                        "detail": f"{d} 数据格式破坏，跳过当前日",
                    }})

        daily_configs_dict_only = {k: v["config_dict"] for k,v in daily_configs.items()}
        final_check = await _check_menu(full_menu, config_dict, daily_configs_dict_only)
        final_metrics = {
            "total_cost": final_check["metrics"].get("total_cost", 0),
            "avg_nutrition_score": final_check["metrics"].get("avg_nutrition_score", 0),
            "repeat_rate": final_check["metrics"].get("repeat_rate", 0),
            "alert_count": final_check["metrics"].get("alert_count", 0),
            "quota_compliance": final_check["metrics"].get("quota_compliance", []),
        }

        final_alerts_readable = [
            f"[{a.get('type', '')}] {a.get('date', '')} "
            f"{a.get('meal_name', '')}"
            f"{'/' + a.get('category', '') if a.get('category') else ''}"
            f"{'/' + a.get('dish_name', '') if a.get('dish_name') else ''}"
            f": {a.get('detail', '')}"
            for a in final_check.get("alerts", [])
        ]

        yield sse("content", {"content": f"✅ 已为您安排好 {len(full_menu)} 天菜单。"})
        yield sse("menu_result", {
            "menu": full_menu,
            "metrics": final_metrics,
            "alerts": final_alerts_readable,
        })
    except asyncio.CancelledError:
        logger.info("Client disconnected, menu generation stopped.")
        # 取消可能还在运行的任务
        raise
    except Exception as e:
        logger.exception("Orchestration encountered fatal error")
        yield sse("error", {"message": f"遭遇致命运行错误：{e}"})
    finally:
        yield "data: [DONE]\n\n"

