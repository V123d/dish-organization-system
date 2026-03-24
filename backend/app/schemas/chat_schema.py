"""
走云智能排菜系统 — Pydantic 请求/响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class DishCategory(BaseModel):
    """菜品分类"""
    name: str
    count: int


class SoupRequirement(BaseModel):
    """汤品要求"""
    description: str = ""


class DiningStyle(BaseModel):
    """用餐方式"""
    type: str = "固定餐标"
    cost_type: Optional[str] = "按食材成本核算"


class MealConstraints(BaseModel):
    """餐次约束"""
    required_ingredients: list[str] = Field(default_factory=list)
    mandatory_dishes: list[str] = Field(default_factory=list)


class DishStructure(BaseModel):
    """菜品结构"""
    categories: list[DishCategory] = Field(default_factory=list)


class MealConfig(BaseModel):
    """单餐次配置"""
    id: str
    meal_name: str
    enabled: bool = True
    diners_count: int = 1000
    intake_rate: int = 60
    budget_per_person: float = 15.0
    dining_style: DiningStyle = Field(default_factory=DiningStyle)
    meal_specific_constraints: MealConstraints = Field(default_factory=MealConstraints)
    dish_structure: DishStructure = Field(default_factory=DishStructure)
    staple_types: list[str] = Field(default_factory=list)
    soup_requirements: SoupRequirement = Field(default_factory=SoupRequirement)
    flavor_preferences: str = ""


class HealthCondition(BaseModel):
    """健康状态"""
    condition: str
    count: int = 0
    enabled: bool = False


class DietaryRestriction(BaseModel):
    """饮食禁忌"""
    restriction: str
    count: int = 0
    enabled: bool = False


class GlobalConstraints(BaseModel):
    """全局约束"""
    red_lines: list[str] = Field(default_factory=list)
    health_conditions: list[HealthCondition] = Field(default_factory=list)
    dietary_restrictions: list[DietaryRestriction] = Field(default_factory=list)


class Schedule(BaseModel):
    """排餐时间"""
    start_date: str
    end_date: str


class ContextOverview(BaseModel):
    """上下文概览"""
    kitchen_class: str = "一类灶"
    city: str = "广州市"
    schedule: Schedule


class MenuPlanConfig(BaseModel):
    """完整排餐配置"""
    context_overview: ContextOverview
    global_hard_constraints: GlobalConstraints = Field(default_factory=GlobalConstraints)
    meals_config: list[MealConfig] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    config: MenuPlanConfig
    current_menu: Optional[dict] = None
    session_id: Optional[str] = None
    history: list[dict] = Field(default_factory=list)


class NotImplementedResponse(BaseModel):
    """待开发功能响应"""
    status: str = "not_implemented"
    message: str


class ConstraintAlert(BaseModel):
    """结构化约束校验告警"""
    type: str  # 例如："COUNT_MISMATCH", "RED_LINE", "BUDGET_OVERFLOW", "DUPLICATE", "CROSS_MEAL_DUPLICATE"
    date: str
    meal_name: str
    category: str = ""
    dish_name: str = ""
    detail: str


class QuotaCompliance(BaseModel):
    """灶别标准达标度"""
    name: str
    actual: float
    standard: float
    rate: float

class CheckMetrics(BaseModel):
    """校验指标汇总"""
    total_cost: float
    avg_nutrition_score: float
    repeat_rate: float
    alert_count: int
    total_dishes: int
    unique_dishes: int
    quota_compliance: list[QuotaCompliance] = Field(default_factory=list)


class ChatSessionCreate(BaseModel):
    """创建或保存对话会话"""
    session_id: Optional[str] = None
    messages: list[dict] = Field(default_factory=list)


class ChatSessionItem(BaseModel):
    """对话会话列表项"""
    id: str
    title: str
    updated_at: str


class ChatSessionDetail(BaseModel):
    """对话会话详情"""
    id: str
    title: str
    messages: list[dict]
    updated_at: str
