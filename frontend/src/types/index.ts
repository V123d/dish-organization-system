/* ========== 走云智能排菜系统 — 核心类型定义 ========== */

/** 灶别标准 */
export type KitchenClass = '一类灶' | '二类灶' | '三类灶';

/** 用餐方式类型 */
export type DiningStyleType = '固定餐标' | '自选打菜' | '自助餐' | '多套餐模式';

/** 成本核算方式 */
export type CostCalculationType = '按食材成本核算' | '按售价核算';

/** 汤性要求 (已废弃) */

/** 菜品分类结构 */
export interface DishCategory {
    name: string;
    count: number;
}

/** 汤品要求 */
export interface SoupRequirement {
    description: string;
}



/** 用餐方式配置 */
export interface DiningStyle {
    type: DiningStyleType;
    cost_type?: CostCalculationType;
    total_dishes?: number;
    avg_picks?: number;
    set_meal_count?: number;
}

/** 餐次特定约束 */
export interface MealSpecificConstraints {
    required_ingredients: string[];
    mandatory_dishes: string[];
}

/** 单餐次配置 */
export interface MealConfig {
    id: string;
    meal_name: string;
    enabled: boolean;
    diners_count: number;
    intake_rate: number;
    budget_per_person: number;
    dining_style: DiningStyle;
    meal_specific_constraints: MealSpecificConstraints;
    dish_structure: {
        categories: DishCategory[];
    };
    staple_types: string[];
    soup_requirements: SoupRequirement;
    flavor_preferences: string;
}

/** 健康状态配置 */
export interface HealthCondition {
    condition: string;
    count: number;
    enabled: boolean;
}

/** 饮食禁忌配置 */
export interface DietaryRestriction {
    restriction: string;
    count: number;
    enabled: boolean;
}

/** 全局硬约束 */
export interface GlobalHardConstraints {
    red_lines: string[];
    health_conditions: HealthCondition[];
    dietary_restrictions: DietaryRestriction[];
}

/** 全局上下文 */
export interface ContextOverview {
    kitchen_class: KitchenClass;
    city: string;
    schedule: {
        start_date: string;
        end_date: string;
    };
}

/** 完整的排菜规则配置 */
export interface MenuPlanConfig {
    context_overview: ContextOverview;
    global_hard_constraints: GlobalHardConstraints;
    meals_config: MealConfig[];
}

/** 菜品信息 */
export interface DishInfo {
    id: number;
    name: string;
    category: string;
    ingredients_quantified: any; // 或者更精确的 interface
    applicable_meals: string[];
    flavor: string;
    cost_per_serving: number;
    nutrition: {
        calories: number;
        protein: number;
        carbs: number;
        fat: number;
    };
    tags: string[];
    is_manual_added?: boolean;
}

/** 单日单格数据 — 日历看板中的单元格 */
export interface CalendarCell {
    date: string;
    meal_name: string;
    category_name: string;
    dishes: DishInfo[];
}

/** 周菜单数据 */
export interface WeeklyMenu {
    [date: string]: {
        [meal_name: string]: {
            [category_name: string]: DishInfo[];
        };
    };
}

/** 灶别标准达标度 */
export interface QuotaCompliance {
    name: string;
    actual: number;
    standard: number;
    rate: number;
}

/** 核心指标汇总 */
export interface DashboardMetrics {
    total_cost: number;
    avg_nutrition_score: number;
    repeat_rate: number;
    alert_count: number;
    alerts?: string[];
    quota_compliance?: QuotaCompliance[];
}

/** 对话消息角色 */
export type MessageRole = 'user' | 'assistant' | 'system';

/** 思考步骤 */
export interface ThinkingStep {
    label: string;
    status: 'pending' | 'running' | 'done' | 'error';
    detail?: string;
}

/** 对话消息 */
export interface ChatMessage {
    id: string;
    role: MessageRole;
    content: string;
    timestamp: number;
    thinking_steps?: ThinkingStep[];
    menu_result?: WeeklyMenu;
    metrics?: DashboardMetrics;
}

/** 智能体信息（来自后端注册表） */
export interface AgentInfo {
    id: string;
    name: string;
    description: string;
    type: 'llm' | 'rule';
    status: 'active' | 'inactive';
    endpoint: string;
}
