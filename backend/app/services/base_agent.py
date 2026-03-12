"""
走云智能排菜系统 — 智能体基类与自动注册机制

所有智能体继承 BaseAgent，通过 __init_subclass__ 实现自动注册。
新增智能体只需：
  1. 创建新文件，继承 BaseAgent
  2. 填写 agent_id / agent_name / agent_description
  3. 实现 execute() 方法
即可自动出现在注册表和 API 路由中，无需手动修改其他文件。
"""
from abc import ABC, abstractmethod
from typing import Any, ClassVar


class AgentRegistry:
    """智能体注册表（全局单例）"""

    _agents: dict[str, "BaseAgent"] = {}

    @classmethod
    def register(cls, agent: "BaseAgent") -> None:
        """注册一个智能体实例"""
        cls._agents[agent.agent_id] = agent

    @classmethod
    def get(cls, agent_id: str) -> "BaseAgent | None":
        """按 ID 获取智能体"""
        return cls._agents.get(agent_id)

    @classmethod
    def list_all(cls) -> list[dict[str, Any]]:
        """返回所有已注册智能体的描述信息（供 /api/agents 接口使用）"""
        return [
            {
                "id": agent.agent_id,
                "name": agent.agent_name,
                "description": agent.agent_description,
                "type": agent.agent_type,
                "status": "active",
                "endpoint": f"/api/agents/{agent.agent_id}",
            }
            for agent in cls._agents.values()
        ]


class BaseAgent(ABC):
    """
    智能体基类。

    子类必须定义以下类变量：
    - agent_id:          唯一标识（kebab-case），同时作为 API 路由名
    - agent_name:        展示名称（中英文皆可）
    - agent_description: 功能描述
    - agent_type:        类型标签（'llm' 表示需要调用大模型，'rule' 表示纯规则引擎）

    子类必须实现：
    - execute(**kwargs) -> dict  执行智能体核心逻辑
    """

    agent_id: ClassVar[str]
    agent_name: ClassVar[str]
    agent_description: ClassVar[str]
    agent_type: ClassVar[str]  # 'llm' | 'rule'

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """自动注册：任何继承 BaseAgent 的子类在导入时即完成注册"""
        super().__init_subclass__(**kwargs)
        # 跳过没有定义 agent_id 的中间抽象类
        if hasattr(cls, "agent_id") and cls.agent_id:
            AgentRegistry.register(cls())

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        执行智能体核心逻辑。

        Args:
            **kwargs: 各智能体自定义的输入参数

        Returns:
            结构化的输出字典
        """
        ...
