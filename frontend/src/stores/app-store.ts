/* ========== Zustand 全局状态管理 ========== */
import { create } from 'zustand';
import type {
    MenuPlanConfig,
    MealConfig,
    ChatMessage,
    WeeklyMenu,
    DashboardMetrics,
    KitchenClass,
    AgentInfo,
} from '../types';
import type { HistoryRecord } from '../services/api';

/** 生成默认的餐次配置 */
function createDefaultMealConfig(name: string, id: string): MealConfig {
    let budget = 100;
    let categories = [
        { name: '大荤', count: 1 },
        { name: '小荤', count: 1 },
        { name: '素菜', count: 2 },
        { name: '主食', count: 1 },
        { name: '汤', count: 1 },
        { name: '水果', count: 1 },
    ];

    if (name === '早餐') {
        budget = 50;
        categories = [
            { name: '主食', count: 1 },
            { name: '素菜', count: 2 },
            { name: '牛奶', count: 1 },
            { name: '甜点', count: 1 },
        ];
    } else if (name === '午餐') {
        budget = 100;
        categories = [
            { name: '大荤', count: 1 },
            { name: '小荤', count: 1 },
            { name: '素菜', count: 1 },
            { name: '凉菜', count: 1 },
            { name: '汤', count: 1 },
            { name: '水果', count: 1 },
        ];
    }

    return {
        id,
        meal_name: name,
        enabled: true,
        diners_count: 500,
        intake_rate: 60,
        budget_per_person: budget,
        dining_style: { type: '固定餐标', cost_type: '按食材成本核算' },
        meal_specific_constraints: { required_ingredients: [], mandatory_dishes: [] },
        dish_structure: { categories },
        staple_types: name === '早餐' ? ['包子', '饺子', '馒头'] : ['米饭'],
        soup_requirements: { description: '' },
        flavor_preferences: '',
    };
}

/** 获取下周一到周日的日期范围 */
function getNextWeekRange(): { start_date: string; end_date: string } {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysUntilNextMonday = dayOfWeek === 0 ? 1 : 8 - dayOfWeek;
    const nextMonday = new Date(today);
    nextMonday.setDate(today.getDate() + daysUntilNextMonday);
    const nextSunday = new Date(nextMonday);
    nextSunday.setDate(nextMonday.getDate() + 6);

    const fmt = (d: Date) => d.toISOString().split('T')[0];
    return { start_date: fmt(nextMonday), end_date: fmt(nextSunday) };
}

interface AppState {
    /** 规则配置 */
    config: MenuPlanConfig;
    setConfig: (config: MenuPlanConfig) => void;
    updateKitchenClass: (kitchen_class: KitchenClass) => void;
    updateCity: (city: string) => void;
    updateSchedule: (start: string, end: string) => void;
    updateMealConfig: (mealId: string, updates: Partial<MealConfig>) => void;
    toggleMeal: (mealId: string) => void;
    addMeal: (name: string) => void;
    removeMeal: (mealId: string) => void;
    updateRedLines: (lines: string[]) => void;

    /** 对话 */
    messages: ChatMessage[];
    addMessage: (msg: ChatMessage) => void;
    updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
    isGenerating: boolean;
    setIsGenerating: (v: boolean) => void;

    /** 菜单结果 */
    weeklyMenu: WeeklyMenu | null;
    setWeeklyMenu: (menu: WeeklyMenu) => void;
    /** 移除单道菜品（支持通过 UI 删除） */
    removeDish: (date: string, mealName: string, category: string, dishId: number) => void;
    /** 增量合并单天菜单（流式生成时逐天调用） */
    mergeWeeklyMenu: (date: string, meals: WeeklyMenu[string]) => void;
    /** 移除某天菜单（约束校验不通过、准备重排时调用） */
    removeDateFromMenu: (date: string) => void;
    /** 清空整个菜单（新一轮生成前调用） */
    clearWeeklyMenu: () => void;
    metrics: DashboardMetrics | null;
    setMetrics: (m: DashboardMetrics) => void;

    historyRecords: HistoryRecord[];
    setHistoryRecords: (records: HistoryRecord[]) => void;

    /** 对话会话列表 */
    currentSessionId: string | null;
    setCurrentSessionId: (id: string | null) => void;
    sessionsList: any[];
    setSessionsList: (sessions: any[]) => void;

    /** 智能体注册表 */
    agents: AgentInfo[];
    setAgents: (agents: AgentInfo[]) => void;

    /** 配置抽屉 */
    configDrawerOpen: boolean;
    setConfigDrawerOpen: (v: boolean) => void;

    /** 停止生成控制 */
    abortController: AbortController | null;
    setAbortController: (ac: AbortController | null) => void;
    stopGeneration: () => void;

    /** 退出登录时重置所有排菜相关状态 */
    resetAll: () => void;
}

const schedule = getNextWeekRange();

export const useAppStore = create<AppState>((set) => ({
    config: {
        context_overview: {
            kitchen_class: '一类灶' as KitchenClass,
            city: '广州市',
            schedule,
        },
        global_hard_constraints: {
            red_lines: [],
            health_conditions: [
                { condition: '糖尿病', count: 0, enabled: false },
                { condition: '高血脂', count: 0, enabled: false },
                { condition: '痛风', count: 0, enabled: false },
                { condition: '高血压', count: 0, enabled: false },
                { condition: '肥胖', count: 0, enabled: false },
                { condition: '贫血', count: 0, enabled: false },
            ],
            dietary_restrictions: [
                { restriction: '海鲜过敏', count: 0, enabled: false },
                { restriction: '乳糖不耐受', count: 0, enabled: false },
                { restriction: '坚果过敏', count: 0, enabled: false },
                { restriction: '不吃猪肉', count: 0, enabled: false },
                { restriction: '不吃牛肉', count: 0, enabled: false },
                { restriction: '完全不吃辣', count: 0, enabled: false },
                { restriction: '清真', count: 0, enabled: false },
                { restriction: '偏好素食', count: 0, enabled: false },
            ],
        },
        meals_config: [
            createDefaultMealConfig('早餐', 'meal-breakfast'),
            createDefaultMealConfig('午餐', 'meal-lunch'),
            createDefaultMealConfig('晚餐', 'meal-dinner'),
        ],
    },

    setConfig: (config) => set({ config }),

    updateKitchenClass: (kitchen_class) =>
        set((s) => ({
            config: { ...s.config, context_overview: { ...s.config.context_overview, kitchen_class } },
        })),

    updateCity: (city) =>
        set((s) => ({
            config: { ...s.config, context_overview: { ...s.config.context_overview, city } },
        })),

    updateSchedule: (start_date, end_date) =>
        set((s) => ({
            config: {
                ...s.config,
                context_overview: { ...s.config.context_overview, schedule: { start_date, end_date } },
            },
        })),

    updateMealConfig: (mealId, updates) =>
        set((s) => ({
            config: {
                ...s.config,
                meals_config: s.config.meals_config.map((m) =>
                    m.id === mealId ? { ...m, ...updates } : m
                ),
            },
        })),

    toggleMeal: (mealId) =>
        set((s) => ({
            config: {
                ...s.config,
                meals_config: s.config.meals_config.map((m) =>
                    m.id === mealId ? { ...m, enabled: !m.enabled } : m
                ),
            },
        })),

    addMeal: (name) =>
        set((s) => ({
            config: {
                ...s.config,
                meals_config: [
                    ...s.config.meals_config,
                    createDefaultMealConfig(name, `meal-${Date.now()}`),
                ],
            },
        })),

    removeMeal: (mealId) =>
        set((s) => ({
            config: {
                ...s.config,
                meals_config: s.config.meals_config.filter((m) => m.id !== mealId),
            },
        })),

    updateRedLines: (red_lines) =>
        set((s) => ({
            config: {
                ...s.config,
                global_hard_constraints: { ...s.config.global_hard_constraints, red_lines },
            },
        })),

    // 对话
    messages: [
        {
            id: 'welcome',
            role: 'assistant',
            content:
                '您好！我是走云智能排菜助手 🍽️ 请告诉我您的排餐需求，例如：\n\n"帮我排下周一到周五的菜单，要求严格控制大荤成本，并规避海鲜过敏原。"',
            timestamp: Date.now(),
        },
    ],
    addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
    updateMessage: (id, updates) =>
        set((s) => ({
            messages: s.messages.map((m) => (m.id === id ? { ...m, ...updates } : m)),
        })),
    isGenerating: false,
    setIsGenerating: (v) => set({ isGenerating: v }),

    // 菜单结果
    weeklyMenu: null,
    setWeeklyMenu: (menu) => set({ weeklyMenu: menu }),
    removeDish: (date, mealName, category, dishId) => set((s) => {
        if (!s.weeklyMenu) return {};
        const updated = { ...s.weeklyMenu };
        if (updated[date]?.[mealName]?.[category]) {
            updated[date][mealName][category] = updated[date][mealName][category].filter(
                (d) => d.id !== dishId
            );
        }
        return { weeklyMenu: updated };
    }),
    mergeWeeklyMenu: (date, meals) =>
        set((s) => ({
            weeklyMenu: {
                ...(s.weeklyMenu ?? {}),
                [date]: meals,
            },
        })),
    removeDateFromMenu: (date) =>
        set((s) => {
            if (!s.weeklyMenu) return {};
            const updated = { ...s.weeklyMenu };
            delete updated[date];
            return { weeklyMenu: updated };
        }),
    clearWeeklyMenu: () => set({ weeklyMenu: null }),
    metrics: null,
    setMetrics: (m) => set({ metrics: m }),

    historyRecords: [],
    setHistoryRecords: (records) => set({ historyRecords: records }),

    // 对话会话列表
    currentSessionId: null,
    setCurrentSessionId: (id) => set({ currentSessionId: id }),
    sessionsList: [],
    setSessionsList: (sessions) => set({ sessionsList: sessions }),

    // 智能体注册表
    agents: [],
    setAgents: (agents) => set({ agents }),

    // 配置抽屉
    configDrawerOpen: false,
    setConfigDrawerOpen: (v) => set({ configDrawerOpen: v }),

    // 停止生成控制
    abortController: null,
    setAbortController: (ac) => set({ abortController: ac }),
    stopGeneration: () => set((s) => {
        if (s.abortController) {
            s.abortController.abort();
        }
        return { isGenerating: false, abortController: null };
    }),

    resetAll: () => set({
        messages: [
            {
                id: 'welcome',
                role: 'assistant',
                content:
                    '您好！我是走云智能排菜助手 🍽️ 请告诉我您的排餐需求，例如：\n\n"帮我排下周一到周五的菜单，要求严格控制大荤成本，并规避海鲜过敏原。"',
                timestamp: Date.now(),
            },
        ],
        weeklyMenu: null,
        metrics: null,
        historyRecords: [],
        currentSessionId: null,
        agents: [],
        configDrawerOpen: false,
        isGenerating: false,
        abortController: null,
    }),
}));
