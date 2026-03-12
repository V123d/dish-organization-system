"""
走云智能排菜系统 — 智能体路由

提供智能体注册表查询和各智能体的独立调用接口。
路由设计为动态注册：新增智能体自动出现在注册表中，
无需手动在此文件添加路由。
"""
from fastapi import APIRouter
from ..services.base_agent import AgentRegistry
from ..schemas.agent_schema import (
    AgentRegistryResponse,
    IntentParseRequest,
    IntentParseResponse,
    ConstraintCheckRequest,
    ConstraintCheckResponse,
    DataEnrichRequest,
    DataEnrichResponse,
    MenuGenerateRequest,
)
from ..schemas.chat_schema import MenuPlanConfig

router = APIRouter(prefix="/api/agents", tags=["智能体"])


@router.get("", response_model=AgentRegistryResponse)
async def get_agent_registry():
    """
    获取所有已注册智能体的信息。

    新增智能体（继承 BaseAgent）后无需修改此接口，
    注册表会自动包含新智能体。
    """
    agents = AgentRegistry.list_all()
    return AgentRegistryResponse(total=len(agents), agents=agents)


@router.post("/intent-parser", response_model=IntentParseResponse)
async def call_intent_parser(request: IntentParseRequest):
    """独立调用：意图解析智能体"""
    agent = AgentRegistry.get("intent-parser")
    if not agent:
        return IntentParseResponse(success=False, error="智能体未注册")
    result = await agent.execute(
        user_message=request.user_message,
        config_json=request.config_json,
    )
    return result


@router.post("/menu-generator")
async def call_menu_generator(request: MenuGenerateRequest):
    """独立调用：菜单生成智能体"""
    agent = AgentRegistry.get("menu-generator")
    if not agent:
        return {"success": False, "error": "智能体未注册"}
    # 将 dict 还原为 MenuPlanConfig 对象
    config = MenuPlanConfig(**request.config)
    result = await agent.execute(
        config=config,
        user_message=request.user_message,
        intent_summary=request.intent_summary,
    )
    return result


@router.post("/constraint-checker", response_model=ConstraintCheckResponse)
async def call_constraint_checker(request: ConstraintCheckRequest):
    """独立调用：约束校验智能体"""
    agent = AgentRegistry.get("constraint-checker")
    if not agent:
        return ConstraintCheckResponse(success=False, passed=False, alerts=["智能体未注册"])
    result = await agent.execute(menu=request.menu, config=request.config)
    return result


@router.post("/data-enrichment", response_model=DataEnrichResponse)
async def call_data_enrichment(request: DataEnrichRequest):
    """独立调用：数据补全智能体"""
    agent = AgentRegistry.get("data-enrichment")
    if not agent:
        return DataEnrichResponse(success=False)
    result = await agent.execute(menu=request.menu)
    return result
