/* ========== 周菜单日历看板 (Calendar Dashboard) ========== */
import { useState, useEffect } from 'react';
import {
    Plus,
    Eye,
    Search,
    X,
    Download,
    Clock
} from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import { getDateRange, getWeekdayLabel, formatDateShort } from '../../utils/date';
import { searchDishes, recalculateMetrics, saveMenuHistory } from '../../services/api';
import type { DishInfo } from '../../types';
import { PreviewModal, NutritionModal, HistoryModal, RecipeModal } from './MenuModals';

export default function CalendarDashboard() {
    const { config, weeklyMenu, metrics, setWeeklyMenu, setMetrics, removeDish } = useAppStore();
    const enabledMeals = config.meals_config.filter((m) => m.enabled);
    const dates = getDateRange(
        config.context_overview.schedule.start_date,
        config.context_overview.schedule.end_date
    );

    const [searchOpen, setSearchOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<DishInfo[]>([]);
    const [searchTarget, setSearchTarget] = useState<{
        date: string;
        meal: string;
        category: string;
    } | null>(null);

    const handleSearch = async (query: string) => {
        setSearchQuery(query);
        if (query.length >= 1) {
            const results = await searchDishes(query);
            setSearchResults(results);
        } else {
            setSearchResults([]);
        }
    };

    // 局部状态用于控制消失动画
    const [displayMenu, setDisplayMenu] = useState<typeof weeklyMenu>(null);
    const [removingDates, setRemovingDates] = useState<Set<string>>(new Set());

    // 模态弹框状态
    const [previewOpen, setPreviewOpen] = useState(false);
    const [nutritionOpen, setNutritionOpen] = useState(false);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [recipeDish, setRecipeDish] = useState<any | null>(null);

    useEffect(() => {
        if (!weeklyMenu) {
            setDisplayMenu(null);
            setRemovingDates(new Set());
            return;
        }

        // 检查是否有被移除的日期（需播放退出动画）
        if (displayMenu) {
            const newlyRemoved = new Set<string>();
            Object.keys(displayMenu).forEach((date) => {
                if (!weeklyMenu[date] && !removingDates.has(date)) {
                    newlyRemoved.add(date);
                }
            });

            if (newlyRemoved.size > 0) {
                setRemovingDates(prev => new Set([...prev, ...newlyRemoved]));
                
                // 等待动画完成后正式从展示区移除
                setTimeout(() => {
                    setDisplayMenu((prev) => {
                        if (!prev) return prev;
                        const next = { ...prev };
                        newlyRemoved.forEach(d => delete next[d]);
                        return next;
                    });
                    setRemovingDates((prev) => {
                        const next = new Set(prev);
                        newlyRemoved.forEach(d => next.delete(d));
                        return next;
                    });
                }, 280);
            }
        }

        // 同步新加入的日期
        setDisplayMenu((prev) => {
            const next = prev ? { ...prev } : {};
            let changed = false;
            Object.keys(weeklyMenu).forEach(date => {
                if (next[date] !== weeklyMenu[date]) {
                    next[date] = weeklyMenu[date];
                    changed = true;
                }
            });
            // 只有当有新增或修改的内容时才触发更新渲染
            return changed ? next : prev;
        });

    }, [weeklyMenu]);

    const handleAddDish = async (dish: DishInfo) => {
        if (!searchTarget || !weeklyMenu) return;
        const { date, meal, category } = searchTarget;
        const updated = { ...weeklyMenu };
        if (!updated[date]) updated[date] = {};
        if (!updated[date][meal]) updated[date][meal] = {};
        if (!updated[date][meal][category]) updated[date][meal][category] = [];
        updated[date][meal][category] = [
            ...updated[date][meal][category],
            { ...dish, is_manual_added: true },
        ];
        setWeeklyMenu(updated);
        setSearchOpen(false);

        // 重新测算指标
        try {
            const res = await recalculateMetrics(updated, config);
            if (res.success) setMetrics(res.metrics);
        } catch (e) {
            console.error("Recalculate failed", e);
        }
    };

    const handleRemoveDish = async (e: React.MouseEvent, date: string, mealName: string, category: string, dishId: number) => {
        e.stopPropagation();
        if (!weeklyMenu) return;
        
        // 计算新的菜单状态
        const updated = { ...weeklyMenu };
        if (updated[date]?.[mealName]?.[category]) {
            updated[date][mealName][category] = updated[date][mealName][category].filter((d) => d.id !== dishId);
        }
        
        removeDish(date, mealName, category, dishId);
        
        // 重新测算
        try {
            const res = await recalculateMetrics(updated, config);
            if (res.success) setMetrics(res.metrics);
        } catch (err) {
            console.error("Recalculate failed", err);
        }
    };

    const handleSaveHistory = async () => {
        if (!weeklyMenu || !metrics) return alert("暂无完整菜单或指标，无法保存");
        try {
            await saveMenuHistory(weeklyMenu, metrics, config);
            alert("✅ 排餐结果已成功保存到历史记录！");
        } catch (err) {
            alert("保存历史记录失败");
        }
    };

    const openSearch = (date: string, meal: string, category: string) => {
        setSearchTarget({ date, meal, category });
        setSearchQuery('');
        setSearchResults([]);
        setSearchOpen(true);
    };

    /** 获取某个单元格中的菜品 */
    const getCellDishes = (date: string, mealName: string, categoryName: string): DishInfo[] => {
        if (!displayMenu) return [];
        return displayMenu[date]?.[mealName]?.[categoryName] || [];
    };

    return (
        <div className="flex flex-col h-full bg-surface">
            {/* 顶部栏 */}
            <div className="px-5 py-3 bg-white border-b border-border-light flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-sm font-bold text-text-primary">周菜单看板</h2>
                    <span className="text-xs text-text-muted">
                        {config.context_overview.schedule.start_date.slice(5)} ~ {config.context_overview.schedule.end_date.slice(5)}
                    </span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <button
                        onClick={() => setPreviewOpen(true)}
                        className="px-3 py-1.5 text-xs font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors flex items-center gap-1"
                    >
                        <Eye size={12} /> 预览完整菜单
                    </button>
                    <button
                        onClick={handleSaveHistory}
                        className="px-3 py-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition-colors flex items-center gap-1"
                    >
                        <Download size={12} /> 保存记录
                    </button>
                    <button
                        onClick={() => setHistoryOpen(true)}
                        className="px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors flex items-center gap-1"
                    >
                        <Clock size={12} /> 历史记录
                    </button>
                </div>
            </div>



            {/* 日历网格 */}
            <div className="flex-1 px-5 pb-4 overflow-auto">
                <div className="bg-white rounded-xl border border-border-light shadow-sm overflow-x-auto">
                    <table className="w-full min-w-max border-collapse text-xs">
                        <thead>
                            <tr className="bg-gradient-to-r from-primary-50 to-accent-50">
                                <th className="px-3 py-2.5 text-left font-semibold text-text-secondary border-b border-r border-border-light w-16">
                                    餐次
                                </th>
                                <th className="px-3 py-2.5 text-left font-semibold text-text-secondary border-b border-r border-border-light w-16">
                                    分类
                                </th>
                                {dates.map((d) => (
                                    <th
                                        key={d}
                                        className="px-2 py-2.5 text-center font-semibold text-text-secondary border-b border-r border-border-light last:border-r-0 min-w-[100px]"
                                    >
                                        <div>{getWeekdayLabel(d)}</div>
                                        <div className="text-[10px] text-text-muted font-normal mt-0.5">{formatDateShort(d)}</div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {enabledMeals.map((meal) =>
                                meal.dish_structure.categories.map((cat, catIdx) => (
                                    <tr
                                        key={`${meal.id}-${catIdx}`}
                                        className="hover:bg-gray-50/50 transition-colors"
                                    >
                                        {/* 餐次名称（合并行） */}
                                        {catIdx === 0 && (
                                            <td
                                                rowSpan={meal.dish_structure.categories.length}
                                                className="px-3 py-2 font-semibold text-text-primary border-b border-r border-border-light bg-gray-50/30 align-top text-center"
                                            >
                                                <span className="writing-mode-vertical inline-block">{meal.meal_name}</span>
                                            </td>
                                        )}
                                        {/* 分类名称 */}
                                        <td className="px-3 py-2 text-text-secondary border-b border-r border-border-light bg-gray-50/10 whitespace-nowrap">
                                            {cat.name}
                                        </td>
                                        {/* 日期单元格 */}
                                        {dates.map((d) => {
                                            const dishes = getCellDishes(d, meal.meal_name, cat.name);
                                            return (
                                                <td
                                                    key={d}
                                                    className="px-1.5 py-1.5 border-b border-r border-border-light last:border-r-0 align-top group min-h-[48px] relative"
                                                >
                                                    {dishes.length > 0 ? (
                                                        <div className="space-y-1">
                                                            {dishes.map((dish) => (
                                                                    <div
                                                                        key={`${dish.id}-${dish.name}`}
                                                                        className={`px-2 py-1.5 rounded-lg text-[11px] cursor-pointer transition-all hover:shadow-sm relative group/dish ${
                                                                            removingDates.has(d) ? 'animate-dish-exit' : 'animate-dish-enter'
                                                                        } ${dish.is_manual_added
                                                                                ? 'bg-warm-50 border border-warm-200 text-warm-700'
                                                                                : 'bg-primary-50/70 border border-primary-100 text-primary-700'
                                                                            }`}
                                                                        onClick={() => setRecipeDish(dish)}
                                                                        title={`${(dish.name || '').replace(/_\d+$/, '')}\n口味: ${dish.flavor || '未知'}`}
                                                                    >
                                                                        <button 
                                                                            onClick={(e) => handleRemoveDish(e, d, meal.meal_name, cat.name, dish.id)}
                                                                            className="absolute -top-1.5 -right-1.5 opacity-0 group-hover/dish:opacity-100 bg-red-100 text-red-500 hover:bg-red-500 hover:text-white rounded-full p-0.5 transition-all shadow-sm z-10"
                                                                        >
                                                                            <X size={10} />
                                                                        </button>
                                                                        <p className="font-medium truncate">{(dish.name || '').replace(/_\d+$/, '')}</p>
                                                                        <p className="text-[9px] text-text-muted mt-0.5">
                                                                            {dish.flavor || '未知'}
                                                                        </p>
                                                                    </div>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <div className="h-10 flex items-center justify-center">
                                                            <span className="text-[10px] text-text-muted">—</span>
                                                        </div>
                                                    )}
                                                    {/* 添加按钮 (hover 显示) */}
                                                    <button
                                                        onClick={() => openSearch(d, meal.meal_name, cat.name)}
                                                        className="absolute bottom-0.5 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity
                              px-2 py-0.5 text-[10px] bg-primary-500 text-white rounded-md flex items-center gap-0.5 hover:bg-primary-600"
                                                    >
                                                        <Plus size={8} /> 添加
                                                    </button>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* 菜品搜索弹窗 */}
            {searchOpen && (
                <>
                    <div
                        className="fixed inset-0 bg-black/20 z-50 backdrop-blur-sm"
                        onClick={() => setSearchOpen(false)}
                    />
                    <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[400px] max-h-[500px] bg-white rounded-2xl shadow-2xl overflow-hidden animate-fade-in">
                        <div className="px-4 py-3 border-b border-border-light flex items-center justify-between">
                            <h3 className="text-sm font-semibold">搜索菜品库</h3>
                            <button onClick={() => setSearchOpen(false)} className="w-6 h-6 rounded hover:bg-gray-100 flex items-center justify-center">
                                <X size={14} />
                            </button>
                        </div>
                        {searchTarget && (
                            <p className="px-4 pt-2 text-[11px] text-text-muted">
                                添加到：{searchTarget.meal} &gt; {searchTarget.category} &gt; {getWeekdayLabel(searchTarget.date)}
                            </p>
                        )}
                        <div className="px-4 py-2">
                            <div className="flex items-center gap-2 border border-border rounded-lg px-3 py-2 focus-within:border-primary-400">
                                <Search size={14} className="text-text-muted" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => handleSearch(e.target.value)}
                                    placeholder="输入菜品名称搜索..."
                                    className="flex-1 bg-transparent outline-none text-sm"
                                    autoFocus
                                />
                            </div>
                        </div>
                        <div className="max-h-[300px] overflow-y-auto px-4 pb-4 space-y-1.5">
                            {searchResults.length > 0 ? (
                                searchResults.map((dish) => (
                                    <div
                                        key={dish.id}
                                        onClick={() => handleAddDish(dish)}
                                        className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-primary-50 cursor-pointer transition-colors"
                                    >
                                        <div>
                                            <p className="text-sm font-medium">{(dish.name || '').replace(/_\d+$/, '')}</p>
                                            <p className="text-[10px] text-text-muted">
                                                {dish.category} · {dish.flavor || '未知'}
                                            </p>
                                        </div>
                                    </div>
                                ))
                            ) : searchQuery ? (
                                <p className="text-xs text-text-muted text-center py-6">未找到匹配菜品</p>
                            ) : (
                                <p className="text-xs text-text-muted text-center py-6">请输入关键词搜索</p>
                            )}
                        </div>
                    </div>
                </>
            )}

            {/* 新功能弹窗 */}
            <PreviewModal isOpen={previewOpen} onClose={() => setPreviewOpen(false)} />
            <NutritionModal isOpen={nutritionOpen} onClose={() => setNutritionOpen(false)} />
            <HistoryModal isOpen={historyOpen} onClose={() => setHistoryOpen(false)} />
            <RecipeModal isOpen={!!recipeDish} onClose={() => setRecipeDish(null)} dish={recipeDish} />
        </div>
    );
}

