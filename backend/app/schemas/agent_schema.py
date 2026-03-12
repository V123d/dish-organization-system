"""
走云智能排菜系统 — 各智能体独立请求/响应 Schema
"""
from pydantic import BaseModel, Field
from typing import Any


class AgentInfo(BaseModel):
    """单个智能体的描述信息"""
    id: str
    name: str
    description: str
    type: str
    status: str
    endpoint: str


class AgentRegistryResponse(BaseModel):
    """智能体注册表响应"""
    total: int
    agents: list[AgentInfo]


class IntentParseRequest(BaseModel):
    """意图解析请求"""
    user_message: str
    config_json: str = Field(default="{}", description="排菜配置 JSON 字符串")


class IntentParseResponse(BaseModel):
    """意图解析响应"""
    success: bool
    parsed_intent: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MenuGenerateRequest(BaseModel):
    """菜单生成请求（独立调用时使用，编排器调用时不经过此 Schema）"""
    user_message: str = "帮我排下周菜单"
    config: dict[str, Any] = Field(description="完整的 MenuPlanConfig JSON")
    intent_summary: str = ""


class ConstraintCheckRequest(BaseModel):
    """约束校验请求"""
    menu: dict[str, Any] = Field(description="菜单 JSON")
    config: dict[str, Any] = Field(description="排菜配置 JSON")


class ConstraintCheckResponse(BaseModel):
    """约束校验响应"""
    success: bool
    passed: bool
    alerts: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class DataEnrichRequest(BaseModel):
    """数据补全请求"""
    menu: dict[str, Any] = Field(description="紧凑格式菜单 JSON")


class DataEnrichResponse(BaseModel):
    """数据补全响应"""
    success: bool
    menu: dict[str, Any] = Field(default_factory=dict)
