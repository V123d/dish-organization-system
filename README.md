# 🍽️ 走云智能排菜系统 (ZouYun Smart Menu Planning System)

> 基于多智能体协同 (Multi-Agent) + 大语言模型 (LLM) 的中学食堂智能排菜系统

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19+-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Qwen](https://img.shields.io/badge/LLM-通义千问_Qwen--max-7C3AED)](https://dashscope.aliyun.com)

---

## 📖 项目简介

走云智能排菜系统是一款面向团餐后厨的 **AI 辅助排菜工具**，旨在将传统的人工排菜流程（通常耗时数小时）缩短至 **分钟级**。系统通过 **"表单结构化约束 + 自然语言对话微调"** 的双轨输入模式，让用户既能通过表单精确配置餐标预算、菜品分类、烹饪工艺等硬性约束，也能通过自然语言灵活表达"下周降温多排驱寒菜"等临时意图。

### 核心业务价值

| 传统人工排菜 | 走云智能排菜 |
|---|---|
| 营养师手动翻查食谱，耗时 2-4 小时 | AI 一键生成一周菜单，耗时 30 秒 |
| 凭经验估算成本，存在超标风险 | 系统自动核算食材成本，实时告警 |
| 难以兼顾多种约束（红线、过敏、营养） | 多智能体交叉校验，100% 满足硬约束 |
| 菜品重复率高，学生抱怨 | 智能去重算法，重复率 ≤ 20% |

---

## 🏗️ 系统架构

### 多智能体架构 (v2.0)

系统采用 **独立智能体 + 编排器** 架构，每个智能体有独立的职责和 API 接口：

```
┌─────────────────────────────────────────────────────────────────┐
│                      前端 (React + TypeScript)                    │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │  日历看板     │  │  对话窗口      │  │  规则配置抽屉       │  │
│  │ CalendarDash  │  │  AgentChat    │  │  ConfigDrawer       │  │
│  │  board       │  │               │  │                     │  │
│  └──────┬───────┘  └───────┬───────┘  └──────────┬──────────┘  │
│         │                  │                     │              │
│  ┌──────┴──────────────────┼─────────────────────┘              │
│  │   智能体状态面板 (AgentPanel) — 动态展示已注册智能体           │
│  └─────────────────────────┼────────────────────────────────────│
│                            │ Zustand 全局状态管理                 │
│                            ▼                                    │
│                     API 服务层 (SSE / REST)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / Server-Sent Events
┌────────────────────────────┼────────────────────────────────────┐
│                        后端 (FastAPI)                            │
│                                                                 │
│  ┌──────────────────── 编排器 (Orchestrator) ──────────────────┐ │
│  │                                                            │ │
│  │  ┌─────────────┐   ┌───────────────┐   ┌───────────────┐  │ │
│  │  │  ① Intent   │ → │  ② Menu       │ → │ ③ Constraint  │  │ │
│  │  │   Parser    │   │   Generator   │   │   Checker     │  │ │
│  │  │  意图解析    │   │   菜单生成     │   │  约束校验      │  │ │
│  │  │  (LLM)     │   │   (LLM)       │   │  (规则引擎)    │  │ │
│  │  └─────────────┘   └───────────────┘   └───────┬───────┘  │ │
│  │                                                │           │ │
│  │                     ┌──────────────────────────┐│           │ │
│  │                     │ 不通过 → 自动重排 (≤2次)  ││           │ │
│  │                     └──────────────────────────┘│           │ │
│  │                                                ▼           │ │
│  │                                       ┌───────────────┐    │ │
│  │                                       │ ④ Data        │    │ │
│  │                                       │  Enrichment   │    │ │
│  │                                       │  数据补全      │    │ │
│  │                                       │  (Python)     │    │ │
│  │                                       └───────────────┘    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ 菜品库 (JSON)   │  │ Pydantic 模型 │  │  智能体注册表     │    │
│  │ 80道中餐菜品    │  │ 类型校验       │  │  自动注册机制     │    │
│  └────────────────┘  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 智能体注册表

| # | 智能体 ID | 名称 | 类型 | 职责 |
|:---:|---|---|:---:|---|
| ① | `intent-parser` | 意图解析智能体 | LLM | 将自然语言指令解析为结构化排菜需求 |
| ② | `menu-generator` | 菜单生成智能体 | LLM | 从菜品库中选菜，组装一周菜单 |
| ③ | `constraint-checker` | 约束校验智能体 | 规则 | 红线扫描、预算检查、重复率计算（确定性校验） |
| ④ | `data-enrichment` | 数据补全智能体 | 规则 | 将紧凑菜单补全为包含完整属性的菜品数据 |

> **可扩展性设计**：新增智能体只需继承 `BaseAgent` 基类并定义 `agent_id`/`agent_name`/`agent_description`，即可自动注册到注册表和 API 路由中，前端面板也会自动展示新智能体。

### 技术栈

| 层级 | 技术 | 版本 | 用途 |
|---|---|---|---|
| **前端框架** | React + TypeScript | 19.x / 5.7 | 组件化 UI 开发，类型安全 |
| **样式方案** | Tailwind CSS | 4.x | 原子化 CSS，快速构建精美 UI |
| **状态管理** | Zustand | 5.x | 轻量级全局状态管理 |
| **构建工具** | Vite | 7.x | 极速 HMR，开箱即用 |
| **图标库** | Lucide React | — | 清爽的开源图标库 |
| **后端框架** | FastAPI | 0.115+ | 高性能异步 API 框架 |
| **LLM 接口** | OpenAI SDK (兼容) | 1.50+ | 调用通义千问 Qwen-max |
| **数据校验** | Pydantic | 2.0+ | 请求/响应模型强类型校验 |

---

## 📂 项目结构

```
走云智能排菜系统/
├── start.bat                              # 🚀 一键启动脚本（双击即可）
├── frontend/                              # 前端 React 应用
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── ContextHeader.tsx     # 全局概览区
│   │   │   │   └── AgentPanel.tsx        # 🆕 智能体状态面板
│   │   │   ├── chat/
│   │   │   │   └── AgentChat.tsx         # 智能对话窗口
│   │   │   ├── config-drawer/
│   │   │   │   └── ConfigDrawer.tsx      # 深度规则配置抽屉
│   │   │   └── calendar/
│   │   │       └── CalendarDashboard.tsx  # 周菜单日历看板
│   │   ├── stores/
│   │   │   └── app-store.ts              # Zustand 全局状态
│   │   ├── services/
│   │   │   └── api.ts                    # API 调用层 (SSE + REST)
│   │   ├── types/
│   │   │   └── index.ts                  # TypeScript 类型定义
│   │   ├── App.tsx                       # 主应用入口
│   │   └── index.css                     # 设计系统
│   └── vite.config.ts                    # Vite 构建配置 (含 SSE 代理)
│
├── backend/                               # 后端 FastAPI 应用
│   ├── app/
│   │   ├── main.py                       # FastAPI 入口 + 路由挂载
│   │   ├── config.py                     # 配置管理 (LLM API Key)
│   │   ├── schemas/
│   │   │   ├── chat_schema.py            # 对话请求/响应模型
│   │   │   └── agent_schema.py           # 🆕 智能体注册表模型
│   │   ├── routers/
│   │   │   ├── chat_router.py            # 🆕 对话 SSE 路由
│   │   │   ├── agent_router.py           # 🆕 智能体独立调用路由
│   │   │   └── dish_router.py            # 🆕 菜品库路由
│   │   ├── services/
│   │   │   ├── base_agent.py             # 🆕 智能体基类 + 自动注册
│   │   │   ├── intent_parser.py          # 🆕 ① 意图解析智能体
│   │   │   ├── menu_generator.py         # 🆕 ② 菜单生成智能体
│   │   │   ├── constraint_checker.py     # 🆕 ③ 约束校验智能体
│   │   │   ├── data_enrichment.py        # 🆕 ④ 数据补全智能体
│   │   │   └── orchestrator.py           # 🆕 多智能体编排器
│   │   └── data/
│   │       └── dish_library.json         # 菜品库 Mock 数据 (80道)
│   ├── .env.example                      # 环境变量模板
│   └── requirements.txt
│
└── README.md
```

---

## 🧠 核心功能实现详解

### 1. 多智能体协同 (Multi-Agent Orchestration)

#### 设计原理

系统由 4 个独立智能体组成，通过编排器 (`orchestrator.py`) 串联协同：

```
用户指令 → ① 意图解析 → ② 菜单生成 → ③ 约束校验 → ④ 数据补全 → 前端展示
  │      (支持日期/餐次提取)               ↑        │            │
  │                                        └── 不通过 ┘ (自动重排)  │
  └────────────────── 携带当前菜单上下文发起多轮局部微调 ──────────────┘
```

#### 智能体自动注册机制

```python
# base_agent.py — 通过 __init_subclass__ 实现零配置注册
class BaseAgent(ABC):
    agent_id: ClassVar[str]
    agent_name: ClassVar[str]
    agent_description: ClassVar[str]
    agent_type: ClassVar[str]  # 'llm' | 'rule'

    def __init_subclass__(cls, **kwargs):
        """子类在导入时即自动注册到全局注册表"""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "agent_id") and cls.agent_id:
            AgentRegistry.register(cls())

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """执行智能体核心逻辑"""
        ...
```

**新增智能体只需 3 步**：
1. 在 `services/` 下创建新文件，继承 `BaseAgent`
2. 定义 `agent_id` / `agent_name` / `agent_description` / `agent_type`
3. 实现 `execute()` 方法
4. 在 `main.py` 添加一行 `from .services import new_agent`

无需修改路由、注册表、前端——全部自动感知。

#### 约束校验智能体（确定性规则引擎）

与其他 LLM 智能体不同，约束校验智能体采用 **纯 Python 确定性逻辑**，保证校验结果 100% 可靠：

- 红线食材扫描：遍历菜单中每道菜的食材列表，匹配全局红线清单
- 预算超标检测：累加每餐食材成本，对比餐标预算
- 重复率计算：统计一周内同名菜品出现次数，计算重复率
- 分类数量匹配：校验每餐每个分类的菜品数量是否符合配置

---

### 2. SSE 流式通信 (Server-Sent Events)

由于 LLM 生成一周菜单需要 **20~40 秒**，系统采用 SSE 实现实时流式通信：

| 阶段 | SSE 事件类型 | 对应智能体 |
|---|---|---|
| 意图解析 | `thinking` | ① Intent Parser |
| 菜单生成 | `thinking` (心跳) | ② Menu Generator |
| 约束校验 | `thinking` | ③ Constraint Checker |
| 数据补全 | `thinking` | ④ Data Enrichment |
| 结果返回 | `content` + `menu_result` | 编排器汇总 |

---

### 3. 前端双轨输入模式

#### 结构化约束 — 深度规则配置抽屉

| 模块 | 内容 |
|---|---|
| **基础属性** | 食堂场景（7种）、城市、日期范围 |
| **动态餐次管理** | 可勾选启用/禁用、自定义名称、动态增删餐次 |
| **餐次内部配置** | 人数/入口率/餐标、菜品分类栅格、主食/汤品/工艺/口味 |
| **特殊人群** | 健康状态（6种）、饮食禁忌（8种）、全局红线 |

#### 自然语言微调 — 智能对话窗口

支持自由文本输入和预设快捷标签。不仅支持首轮全局菜单生成，还支持在已有菜单基础上进行**多轮对话与局部微调**（如"把周四的午餐全换成素菜"）。对话窗口会实时流式展示智能体的思考步骤，并在违反硬性约束时展示详细的**结构化违规告警**。

---

### 4. 智能体状态面板

前端右侧新增 **智能体矩阵面板**，自动从 `GET /api/agents` 获取注册表数据，展示：
- 每个智能体的名称和在线状态
- 智能体类型标签（AI = LLM 驱动 / 规则 = 确定性逻辑）
- 新增智能体自动出现，无需前端代码改动

---

### 5. 菜品库

菜品库包含 **80 道标准中餐菜品**，覆盖大荤(19)、小荤(18)、素菜(20)、主食(10)、汤(13) 五大分类。每道菜品包含 ID、名称、分类、食材、工艺、口味、成本、营养和标签等完整属性。

---

### 6. 最新架构特性 (v2.1)

- **多轮会话与局部重排 (Multi-Turn Menu Edits)**：支持在已生成的一周菜单基础上，通过自然语言发出局部修改指令（如“把周四的午餐全部换成素菜”）。系统会自动携带当前菜单上下文，**仅针对受影响的餐次/菜品重新生成**，并保证全局原有结构不变。
- **精细化意图解析 (Enhanced Intent Parsing)**：意图解析智能体现已支持识别带有**特定日期**和**特定餐次**定语的复杂指令，使得下游的菜单生成器和约束校验器能执行精准的局部级操作。
- **结构化约束告警 (Structured Constraint Alerts)**：告别黑盒报错模式。当排菜结果不满足硬性约束且自动重试（≤2次）仍无法满足时，系统将通过 SSE 返回详细的结构化告警。前端会展示明确的违规类型（如 `COUNT_MISMATCH`、`RED_LINE`、`BUDGET_OVERFLOW` 等）、对应日期餐次及具体详情，极大提升了 AI 行为的可解释性。

---

## 🚀 快速开始

### 环境要求

- **Node.js** ≥ 18.x
- **Python** ≥ 3.10
- **通义千问 API Key** ([申请地址](https://dashscope.console.aliyun.com/))

### 方式一：一键启动 (推荐)

```bash
# 1. 克隆项目
git clone https://github.com/V123d/dish-organization-system.git
cd dish-organization-system

# 2. 配置 API Key
copy backend\.env.example backend\.env
# 编辑 backend\.env，将 LLM_API_KEY 替换为你的 API Key

# 3. 双击启动
start.bat
```

### 方式二：手动启动

**终端 1 — 启动后端：**
```bash
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2 — 启动前端：**
```bash
cd frontend
npm install
npm run dev
```

### 访问系统

| 地址 | 说明 |
|---|---|
| http://localhost:5173 | 前端页面 |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/api/agents | 智能体注册表 |
| http://localhost:8000/api/health | 健康检查 |

---

## 📋 使用指南

### 基本排菜流程

1. **配置约束**：点击 ⚙️ 打开规则配置抽屉，设置场景/城市/餐次/预算/红线等
2. **发送指令**：在对话框输入自然语言指令（如 "帮我排下周的午晚餐菜单"）
3. **查看结果**：观察右侧 4 个智能体依次工作的思考动效，左侧日历看板自动填充菜品
4. **人工微调**：鼠标悬浮日历单元格，点击"+"搜索替换菜品

---

## 🔌 API 接口文档

### 智能体接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/agents` | 获取所有已注册智能体信息 |
| `POST` | `/api/agents/intent-parser` | 独立调用意图解析 |
| `POST` | `/api/agents/menu-generator` | 独立调用菜单生成 |
| `POST` | `/api/agents/constraint-checker` | 独立调用约束校验 |
| `POST` | `/api/agents/data-enrichment` | 独立调用数据补全 |

### 编排接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/chat/send` | 智能排菜对话 (SSE 流式，串联全部智能体) |

### 菜品库接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/dishes/search?q=xxx` | 搜索菜品库 |
| `GET` | `/api/dishes/library` | 获取完整菜品库 (80道) |
| `GET` | `/api/health` | 健康检查（含智能体数量） |

### 占位接口 (待开发)

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/report/nutrition` | 营养报告生成 |
| `GET` | `/api/report/recipe/:id` | 定量配方查看 |
| `POST` | `/api/pricing/sync` | 生鲜时价同步 |
| `POST` | `/api/inventory/sync` | 库存数据同步 |
| `POST` | `/api/plan/save` | 保存排餐计划 |
| `GET` | `/api/plan/:id` | 获取排餐计划 |

---

## 🗺️ 后续开发路线

### Phase 2 — 智能体增强
- [ ] 新增 Nutrition Analyzer（营养分析智能体）— 基于食物成分表精确计算 DRIs 达标率
- [ ] 新增 Cost Controller（成本控制智能体）— 对接实时食材价格
- [ ] 新增 Feedback Learner（反馈学习智能体）— 数据闭环优化推荐

### Phase 3 — 数据层完善
- [ ] 接入真实食材定价 API (供应商 ERP)
- [ ] 持久化存储 (SQLite/PostgreSQL) 替代 JSON Mock
- [ ] 用户认证与多食堂管理

### Phase 4 — 生产化
- [ ] 定量配方与采购清单自动生成
- [ ] 历史菜单分析与智能推荐
- [ ] Docker 容器化部署
- [ ] 移动端适配

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [通义千问 Qwen](https://dashscope.aliyun.com/) — 提供大语言模型 API
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架
- [React](https://react.dev/) — 前端 UI 框架
- [Tailwind CSS](https://tailwindcss.com/) — 原子化 CSS 框架
- [Zustand](https://github.com/pmndrs/zustand) — 轻量状态管理
- [Lucide](https://lucide.dev/) — 开源图标库
