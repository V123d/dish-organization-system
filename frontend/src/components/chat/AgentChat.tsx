/* ========== 智能排菜对话窗口 (Agent Chat Window) ========== */
import { useState, useRef, useEffect } from 'react';
import { Send, Settings2, CheckCircle2, Loader2, AlertCircle, Bot, User } from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import { sendChatMessage, saveChatSession } from '../../services/api';
import type { ConstraintAlert } from '../../services/api';
import { generateId } from '../../utils/date';
import type { ThinkingStep } from '../../types';

/** 快捷指令标签 */
const QUICK_PROMPTS = [
    '#提高蛋白质',
    '#控制成本在8元内',
    '#多排清淡菜',
    '#下周大降温多排驱寒菜',
    '#少油少盐',
    '#用鸡鸭鱼替换猪肉',
];

export default function AgentChat() {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const {
        messages,
        addMessage,
        updateMessage,
        isGenerating,
        setIsGenerating,
        config,
        weeklyMenu,
        setWeeklyMenu,
        setMetrics,
        mergeWeeklyMenu,
        removeDateFromMenu,
        clearWeeklyMenu,
        setConfigDrawerOpen,
        setAbortController,
        stopGeneration,
    } = useAppStore();

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        const text = input.trim();
        if (!text || isGenerating) return;

        // 添加用户消息
        const userMsgId = generateId();
        addMessage({
            id: userMsgId,
            role: 'user',
            content: text,
            timestamp: Date.now(),
        });
        setInput('');

        // 添加 Agent 回复占位
        const agentMsgId = generateId();
        const thinkingSteps: ThinkingStep[] = [
            { label: '意图解析', status: 'pending' },
            { label: '生成菜单', status: 'pending' },
            { label: '成本计算', status: 'pending' },
            { label: '约束校验', status: 'pending' },
        ];
        addMessage({
            id: agentMsgId,
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
            thinking_steps: thinkingSteps,
        });
        setIsGenerating(true);
        // 记录在清空前抓取的当前菜单状态，以便后端只做局部修改
        const currentMenuContext = weeklyMenu;
        
        // 生成前先清空上轮菜单，准备流式填充（UI表现）
        clearWeeklyMenu();

        const controller = new AbortController();
        setAbortController(controller);

        let accumulatedContent = '';
        const historyForApi = messages.filter(m => m.id !== 'welcome').map(m => ({ role: m.role, content: m.content }));

        await sendChatMessage(
            text,
            historyForApi,
            config,
            currentMenuContext,
            // onThinkingStep
            (step) => {
                // 使用模糊匹配，兼容后端动态附加日期后缀或组合标签（如 "生成菜单 (2026-03-24)" 或 "数据补全.../食材成本计算"）
                const matchLabel = (existing: string, incoming: string) =>
                    existing === incoming || incoming.includes(existing);
                updateMessage(agentMsgId, {
                    thinking_steps: thinkingSteps.map((s) =>
                        matchLabel(s.label, step.label)
                            ? { ...s, status: step.status as ThinkingStep['status'], detail: step.detail }
                            : s
                    ),
                });
                // 更新本地引用
                const idx = thinkingSteps.findIndex((s) => matchLabel(s.label, step.label));
                if (idx >= 0) {
                    thinkingSteps[idx] = { ...thinkingSteps[idx], status: step.status as ThinkingStep['status'], detail: step.detail };
                }
            },
            // onContent
            (content) => {
                accumulatedContent += content;
                updateMessage(agentMsgId, { content: accumulatedContent });
            },
            // onMenuResult
            (menu, metrics) => {
                setWeeklyMenu(menu);
                setMetrics(metrics);
                updateMessage(agentMsgId, { menu_result: menu, metrics });
            },
            // onDone
            async () => {
                setIsGenerating(false);
                try {
                    const latestMessages = useAppStore.getState().messages;
                    const sid = useAppStore.getState().currentSessionId;
                    const res = await saveChatSession(sid, latestMessages);
                    if (res.success && res.session_id) {
                        useAppStore.getState().setCurrentSessionId(res.session_id);
                    }
                } catch (e) {
                    console.error("保存会话失败", e);
                }
            },
            // onError
            (error) => {
                updateMessage(agentMsgId, {
                    content: `⚠️ 排菜失败：${error}`,
                    thinking_steps: thinkingSteps.map((s) =>
                        s.status === 'running' ? { ...s, status: 'error' as const } : s
                    ),
                });
                setIsGenerating(false);
            },
            // onMenuUpdate: 逐天增量填充日历看板
            (date, meals) => {
                mergeWeeklyMenu(date, meals);
            },
            // onMenuRemove: 约束不通自动清除旧菜单，触发消失动画
            (date) => {
                removeDateFromMenu(date);
            },
            // onConstraintAlert: 显示具体不合格项
            (date, alerts: ConstraintAlert[], attempt) => {
                const alertsText = alerts.map(a => `[${a.type}] ${a.dish_name || a.category}: ${a.detail}`).join('；');
                const detail = `⚠️ ${date} 第${attempt}轮检查发现: ${alertsText}`;
                updateMessage(agentMsgId, {
                    thinking_steps: thinkingSteps.map((s) =>
                        s.label === '约束校验'
                            ? { ...s, status: 'error' as const, detail }
                            : s
                    ),
                });
            },
            controller.signal
        );
        setAbortController(null);
    };

    const handleQuickPrompt = (prompt: string) => {
        setInput((prev) => (prev ? `${prev} ${prompt}` : prompt.replace('#', '')));
    };

    return (
        <div className="flex flex-col h-full">
            {/* 对话标题 */}
            <div className="px-4 py-3 border-b border-border-light flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary-400 to-accent-500 flex items-center justify-center">
                        <Bot size={14} className="text-white" />
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-text-primary">排菜智能体 (Agent)</p>
                        <p className="text-[10px] text-primary-500">已连接辅助排菜引擎</p>
                    </div>
                </div>
                <button
                    onClick={() => setConfigDrawerOpen(true)}
                    className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center transition-colors"
                    title="打开规则配置"
                >
                    <Settings2 size={16} className="text-text-secondary" />
                </button>
            </div>

            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                {messages.map((msg) => (
                    <div key={msg.id} className={`flex gap-2.5 animate-fade-in ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                        {/* 头像 */}
                        <div
                            className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${msg.role === 'user'
                                    ? 'bg-gradient-to-br from-blue-400 to-blue-600'
                                    : 'bg-gradient-to-br from-primary-400 to-accent-500'
                                }`}
                        >
                            {msg.role === 'user' ? (
                                <User size={13} className="text-white" />
                            ) : (
                                <Bot size={13} className="text-white" />
                            )}
                        </div>

                        {/* 消息体 */}
                        <div className={`max-w-[85%] ${msg.role === 'user' ? 'text-right' : ''}`}>
                            {/* 思考步骤 */}
                            {msg.thinking_steps && (
                                <div className="mb-2 space-y-1">
                                    {msg.thinking_steps.map((step, i) => (
                                        <div key={i} className="flex items-center gap-1.5 text-xs">
                                            {step.status === 'done' && <CheckCircle2 size={12} className="text-primary-500" />}
                                            {step.status === 'running' && <Loader2 size={12} className="text-primary-500 animate-spin" />}
                                            {step.status === 'pending' && <div className="w-3 h-3 rounded-full border border-gray-300" />}
                                            {step.status === 'error' && <AlertCircle size={12} className="text-red-400" />}
                                            <span className={step.status === 'done' ? 'text-primary-600' : step.status === 'running' ? 'text-primary-500 font-medium' : 'text-text-muted'}>
                                                {step.label}
                                            </span>
                                            {step.detail && <span className="text-text-muted">— {step.detail}</span>}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* 消息内容 */}
                            {msg.content && (
                                <div
                                    className={`inline-block px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${msg.role === 'user'
                                            ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-br-md'
                                            : 'bg-white border border-border-light shadow-sm rounded-bl-md text-text-primary'
                                        }`}
                                >
                                    {msg.content}
                                </div>
                            )}

                        </div>
                    </div>
                ))}

                {/* 加载动画 */}
                {isGenerating && (
                    <div className="flex gap-1.5 items-center pl-10 text-text-muted">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '0ms' }} />
                        <div className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '200ms' }} />
                        <div className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse-dot" style={{ animationDelay: '400ms' }} />
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* 快捷指令 */}
            <div className="px-4 py-2 flex gap-1.5 flex-wrap border-t border-border-light bg-white/50">
                {QUICK_PROMPTS.map((p) => (
                    <button
                        key={p}
                        onClick={() => handleQuickPrompt(p)}
                        className="px-2.5 py-1 text-[11px] bg-primary-50 text-primary-600 rounded-full hover:bg-primary-100 transition-colors whitespace-nowrap"
                    >
                        {p}
                    </button>
                ))}
            </div>

            {/* 输入区域 */}
            <div className="px-4 py-3 border-t border-border-light bg-white">
                <div className="flex items-center gap-2 bg-surface rounded-xl border border-border px-3 py-2 focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 transition-all">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                        placeholder="输入自然语言指令，Agent自动解析..."
                        className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder:text-text-muted"
                        disabled={isGenerating}
                    />
                    {isGenerating ? (
                        <button
                            onClick={stopGeneration}
                            className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center text-red-500 hover:bg-red-100 transition-all border border-red-200"
                            title="停止生成"
                        >
                            <div className="w-3 h-3 bg-red-500 rounded-[2px]" />
                        </button>
                    ) : (
                        <button
                            onClick={handleSend}
                            disabled={!input.trim()}
                            className="w-8 h-8 rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 flex items-center justify-center text-white disabled:opacity-40 hover:shadow-md transition-all disabled:hover:shadow-none"
                        >
                            <Send size={14} />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
