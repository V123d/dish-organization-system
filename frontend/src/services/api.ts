/* ========== API 调用服务层 ========== */
import type { MenuPlanConfig, WeeklyMenu, DashboardMetrics, DishInfo, AgentInfo } from '../types';
import { useAuthStore } from '../stores/auth-store';
import { useAppStore } from '../stores/app-store';

const API_BASE = '/api';

/** 带鉴权的 fetch 拦截器 */
async function fetchWithAuth(url: string, options: RequestInit = {}) {
    const token = useAuthStore.getState().token;
    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
        useAuthStore.getState().logout();
        useAppStore.getState().resetAll();
        throw new Error("认证已过期，请重新登录");
    }
    return res;
}

/** 账号密码登录 */
export async function login(username: string, password: string) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
    });
    if (!res.ok) {
        const err = await res.json();
        throw { response: { data: err } };
    }
    return res.json();
}

/** 账号注册 */
export async function register(username: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
        const err = await res.json();
        throw { response: { data: err } };
    }
    return res.json();
}

/** 约束告警项结构 */
export interface ConstraintAlert {
    type: string;
    date: string;
    meal_name: string;
    category: string;
    dish_name: string;
    detail: string;
}

/** 发送排菜指令（SSE 流式返回） */
export async function sendChatMessage(
    userMessage: string,
    history: any[],
    config: MenuPlanConfig,
    currentMenu: WeeklyMenu | null,
    onThinkingStep: (step: { label: string; status: string; detail?: string }) => void,
    onContent: (content: string) => void,
    onMenuResult: (menu: WeeklyMenu, metrics: DashboardMetrics) => void,
    onDone: () => void,
    onError: (error: string) => void,
    onMenuUpdate?: (date: string, meals: WeeklyMenu[string]) => void,
    onMenuRemove?: (date: string) => void,
    onConstraintAlert?: (date: string, alerts: ConstraintAlert[], attempt: number) => void,
    abortSignal?: AbortSignal,
): Promise<void> {
    try {
        const bodyObj: any = { message: userMessage, config, history };
        if (currentMenu) {
            bodyObj.current_menu = currentMenu;
        }

        const response = await fetchWithAuth(`${API_BASE}/chat/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyObj),
            signal: abortSignal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') {
                        onDone();
                        return;
                    }
                    try {
                        const parsed = JSON.parse(data);
                        switch (parsed.type) {
                            case 'thinking':
                                onThinkingStep(parsed.step);
                                break;
                            case 'content':
                                onContent(parsed.content);
                                break;
                            case 'menu_result':
                                onMenuResult(parsed.menu, {
                                    ...parsed.metrics,
                                    alerts: parsed.alerts ?? [],
                                });
                                break;
                            case 'menu_update':
                                // 逐天增量填充日历看板
                                onMenuUpdate?.(parsed.date, parsed.meals);
                                break;
                            case 'menu_partial_update':
                                // 流式生成增量渲染
                                onMenuUpdate?.(parsed.date, parsed.meals);
                                break;
                            case 'menu_remove':
                                // 约束校验不通过，移除旧菜品（触发消失动画）
                                onMenuRemove?.(parsed.date);
                                break;
                            case 'constraint_alert':
                                // 约束校验的具体不合格项
                                onConstraintAlert?.(parsed.date, parsed.alerts, parsed.attempt ?? 1);
                                break;
                            case 'error':
                                onError(parsed.message);
                                break;
                        }
                    } catch {
                        // 非 JSON 数据，忽略
                    }
                }
            }
        }
        onDone();
    } catch (err: any) {
        if (err.name === 'AbortError') {
            console.log('Stream generation aborted by user.');
            return;
        }
        onError(err instanceof Error ? err.message : '网络请求失败');
    }
}

/** 搜索菜品库 */
export async function searchDishes(query: string): Promise<DishInfo[]> {
    try {
        const res = await fetchWithAuth(`${API_BASE}/dishes/search?q=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('搜索失败');
        return await res.json();
    } catch {
        return [];
    }
}

/** 获取菜品库 */
export async function getDishLibrary(): Promise<DishInfo[]> {
    try {
        const res = await fetchWithAuth(`${API_BASE}/dishes/library`);
        if (!res.ok) throw new Error('获取菜品库失败');
        return await res.json();
    } catch {
        return [];
    }
}

/** 获取所有菜品分类 */
export async function getDishCategories(): Promise<string[]> {
    try {
        const res = await fetchWithAuth(`${API_BASE}/dishes/categories`);
        if (!res.ok) throw new Error('获取分类失败');
        return await res.json();
    } catch {
        return [];
    }
}

/** 通用待开发提示 */
export function showNotImplemented(featureName: string): void {
    // 使用简单的 toast 通知
    const toast = document.createElement('div');
    toast.className =
        'fixed top-4 right-4 z-[9999] px-5 py-3 bg-warm-500 text-white rounded-xl shadow-lg animate-slide-up text-sm font-medium';
    toast.textContent = `🚧 "${featureName}" 功能待开发`;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.transition = 'opacity 0.3s';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

/** 获取智能体注册表（动态读取，新增智能体自动出现） */
export async function getAgentRegistry(): Promise<AgentInfo[]> {
    try {
        const res = await fetchWithAuth(`${API_BASE}/agents`);
        if (!res.ok) throw new Error('获取智能体注册表失败');
        const data = await res.json();
        return data.agents || [];
    } catch {
        return [];
    }
}

/** 重新计算菜单指标 */
export async function recalculateMetrics(menu: WeeklyMenu, config: MenuPlanConfig): Promise<{ success: boolean; metrics: DashboardMetrics }> {
    const res = await fetchWithAuth(`${API_BASE}/menu/recalculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ menu, config }),
    });
    if (!res.ok) throw new Error('重新计算失败');
    return await res.json();
}

export interface HistoryRecord {
    id: string;
    name: string;
    timestamp: string;
    metrics: DashboardMetrics;
}

export async function saveMenuHistory(menu: WeeklyMenu, metrics: DashboardMetrics, config: MenuPlanConfig, name?: string): Promise<{ success: boolean; id: string }> {
    const res = await fetchWithAuth(`${API_BASE}/menu/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ menu, metrics, config, name }),
    });
    if (!res.ok) throw new Error('保存历史记录失败');
    return await res.json();
}

export async function getHistoryList(): Promise<HistoryRecord[]> {
    const res = await fetchWithAuth(`${API_BASE}/menu/history`);
    if (!res.ok) throw new Error('获取历史记录失败');
    const data = await res.json();
    return data.records || [];
}

export async function getHistoryDetail(id: string): Promise<{ menu: WeeklyMenu; metrics: DashboardMetrics; config: MenuPlanConfig }> {
    const res = await fetchWithAuth(`${API_BASE}/menu/history/${id}`);
    if (!res.ok) throw new Error('获取详情失败');
    const data = await res.json();
    return data.data || {};
}

// ==========================
// 会话记录接口 (Chat Sessions)
// ==========================

export async function saveChatSession(sessionId: string | null, messages: any[]): Promise<{ success: boolean; session_id: string; title: string }> {
    const res = await fetchWithAuth(`${API_BASE}/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, messages }),
    });
    if (!res.ok) throw new Error('保存会话失败');
    return await res.json();
}

export async function getChatSessionsList(): Promise<any[]> {
    const res = await fetchWithAuth(`${API_BASE}/chat/sessions`);
    if (!res.ok) throw new Error('获取会话列表失败');
    const data = await res.json();
    return data.sessions || [];
}

export async function getChatSessionDetail(sessionId: string): Promise<any> {
    const res = await fetchWithAuth(`${API_BASE}/chat/sessions/${sessionId}`);
    if (!res.ok) throw new Error('获取会话详情失败');
    const data = await res.json();
    return data.data || {};
}

export async function deleteChatSession(sessionId: string): Promise<void> {
    const res = await fetchWithAuth(`${API_BASE}/chat/sessions/${sessionId}`, {
        method: 'DELETE',
    });
    if (!res.ok) throw new Error('删除会话失败');
}

