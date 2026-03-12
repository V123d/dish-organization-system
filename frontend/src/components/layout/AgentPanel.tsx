/* ========== 智能体状态面板 ========== */
import { useEffect } from 'react';
import { Bot, Brain, ShieldCheck, Database, Cpu } from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import { getAgentRegistry } from '../../services/api';
import type { AgentInfo } from '../../types';

/** 根据智能体 ID 返回对应图标 */
function getAgentIcon(agentId: string) {
    switch (agentId) {
        case 'intent-parser':
            return <Brain className="w-4 h-4" />;
        case 'menu-generator':
            return <Bot className="w-4 h-4" />;
        case 'constraint-checker':
            return <ShieldCheck className="w-4 h-4" />;
        case 'data-enrichment':
            return <Database className="w-4 h-4" />;
        default:
            return <Cpu className="w-4 h-4" />;
    }
}

/** 提取智能体中文名（"English / 中文" → "中文"） */
function getDisplayName(agent: AgentInfo): string {
    const parts = agent.name.split('/');
    return parts.length > 1 ? parts[1].trim() : agent.name;
}

export default function AgentPanel() {
    const agents = useAppStore((s) => s.agents);
    const setAgents = useAppStore((s) => s.setAgents);

    useEffect(() => {
        getAgentRegistry().then((list) => {
            if (list.length > 0) setAgents(list);
        });
    }, [setAgents]);

    if (agents.length === 0) return null;

    return (
        <div className="px-3 py-2">
            <div className="flex items-center gap-1.5 mb-2">
                <Cpu className="w-3.5 h-3.5 text-primary-400" />
                <span className="text-xs font-semibold text-gray-400 tracking-wide uppercase">
                    智能体矩阵
                </span>
                <span className="ml-auto text-[10px] text-gray-500 bg-gray-800/50 px-1.5 py-0.5 rounded-full">
                    {agents.length} 个已注册
                </span>
            </div>
            <div className="space-y-1">
                {agents.map((agent) => (
                    <div
                        key={agent.id}
                        className="group flex items-center gap-2 px-2.5 py-1.5 rounded-lg
                                   bg-gray-800/30 hover:bg-gray-800/60 transition-colors cursor-default"
                        title={agent.description}
                    >
                        <div className={`flex-shrink-0 ${
                            agent.type === 'llm' ? 'text-purple-400' : 'text-emerald-400'
                        }`}>
                            {getAgentIcon(agent.id)}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-gray-200 truncate">
                                {getDisplayName(agent)}
                            </div>
                        </div>
                        <div className="flex items-center gap-1">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                                agent.type === 'llm'
                                    ? 'bg-purple-500/20 text-purple-300'
                                    : 'bg-emerald-500/20 text-emerald-300'
                            }`}>
                                {agent.type === 'llm' ? 'AI' : '规则'}
                            </span>
                            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
