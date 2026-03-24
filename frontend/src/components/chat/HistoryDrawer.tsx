import { useState, useEffect } from 'react';
import { X, MessageSquare, Plus, Trash2, Clock, Loader2 } from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import { getChatSessionsList, getChatSessionDetail, deleteChatSession } from '../../services/api';

export default function HistoryDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const { currentSessionId, setCurrentSessionId, sessionsList, setSessionsList, resetAll } = useAppStore();
    const [loading, setLoading] = useState(false);
    const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);

    const loadSessions = async () => {
        setLoading(true);
        try {
            const list = await getChatSessionsList();
            setSessionsList(list);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            loadSessions();
        }
    }, [isOpen]);

    const handleNewChat = () => {
        resetAll();
        onClose();
    };

    const handleSelectSession = async (id: string) => {
        if (id === currentSessionId) {
            onClose();
            return;
        }
        setLoadingDetailId(id);
        try {
            const detail = await getChatSessionDetail(id);
            resetAll();
            setCurrentSessionId(id);
            useAppStore.setState({ messages: detail.messages || [] });
            onClose();
        } catch (e) {
            console.error("加载对话失败", e);
        } finally {
            setLoadingDetailId(null);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        try {
            await deleteChatSession(id);
            if (id === currentSessionId) {
                resetAll();
            }
            loadSessions();
        } catch (e) {
            console.error("删除失败", e);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex animate-fade-in shadow-2xl">
            <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
            
            <div className="relative w-80 bg-white h-full flex flex-col border-r border-border-light shadow-xl">
                <div className="p-4 border-b border-border-light flex items-center justify-between">
                    <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                        <Clock size={16} className="text-primary-600" />
                        历史对话
                    </h2>
                    <button onClick={onClose} className="p-1.5 text-text-muted hover:bg-gray-100 rounded-lg">
                        <X size={16} />
                    </button>
                </div>
                
                <div className="p-3">
                    <button
                        onClick={handleNewChat}
                        className="w-full flex items-center gap-2 px-3 py-2.5 bg-primary-50 text-primary-700 hover:bg-primary-100 rounded-xl transition-colors text-sm font-medium"
                    >
                        <Plus size={16} />
                        开启新对话
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-3 space-y-1">
                    {loading ? (
                        <div className="flex justify-center p-4"><Loader2 size={16} className="animate-spin text-text-muted" /></div>
                    ) : sessionsList.length === 0 ? (
                        <div className="text-center py-6 text-sm text-text-muted">暂无历史记录</div>
                    ) : (
                        sessionsList.map(session => (
                            <div
                                key={session.id}
                                onClick={() => handleSelectSession(session.id)}
                                className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors ${
                                    session.id === currentSessionId 
                                        ? 'bg-primary-50 border border-primary-200' 
                                        : 'hover:bg-gray-50 border border-transparent'
                                }`}
                            >
                                <div className="flex items-center gap-2 min-w-0 pr-2">
                                    <MessageSquare size={14} className={session.id === currentSessionId ? 'text-primary-600 shrink-0' : 'text-text-muted shrink-0'} />
                                    <span className={`text-sm truncate ${session.id === currentSessionId ? 'text-primary-700 font-medium' : 'text-text-primary'}`} title={session.title}>
                                        {session.title || '新对话'}
                                    </span>
                                </div>
                                <div className="flex items-center">
                                    {loadingDetailId === session.id ? (
                                        <Loader2 size={14} className="animate-spin text-primary-500" />
                                    ) : (
                                        <button 
                                            onClick={(e) => handleDelete(e, session.id)}
                                            className="opacity-0 group-hover:opacity-100 p-1 text-text-muted hover:text-red-500 hover:bg-red-50 rounded transition-all"
                                            title="删除"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
