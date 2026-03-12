/* ========== 主应用入口 ========== */
import './index.css';
import ContextHeader from './components/layout/ContextHeader';
import AgentPanel from './components/layout/AgentPanel';
import AgentChat from './components/chat/AgentChat';
import CalendarDashboard from './components/calendar/CalendarDashboard';
import ConfigDrawer from './components/config-drawer/ConfigDrawer';

function App() {
  return (
    <div className="h-screen flex flex-col bg-surface">
      {/* 全局顶部栏 */}
      <header className="h-11 bg-white border-b border-border-light flex items-center px-5 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-sm">
            <span className="text-white text-sm">🍽️</span>
          </div>
          <h1 className="text-sm font-bold text-text-primary tracking-wide">走云智能后厨</h1>
          <span className="text-xs text-text-muted">智能排菜系统 v2.0 · 多智能体架构</span>
        </div>
      </header>

      {/* 主体内容：左日历 + 右对话 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧: 日历看板 (占大部分) */}
        <main className="flex-1 min-w-0 overflow-hidden">
          <CalendarDashboard />
        </main>

        {/* 右侧: 智能体面板 + 对话 + 概览区 */}
        <aside className="w-[380px] shrink-0 border-l border-border-light bg-white flex flex-col overflow-hidden">
          {/* 全局概览 */}
          <ContextHeader />
          {/* 智能体状态面板 */}
          <div className="border-b border-border-light bg-gray-900/95">
            <AgentPanel />
          </div>
          {/* 对话窗口 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <AgentChat />
          </div>
        </aside>
      </div>

      {/* 配置抽屉 (浮层) */}
      <ConfigDrawer />
    </div>
  );
}

export default App;
