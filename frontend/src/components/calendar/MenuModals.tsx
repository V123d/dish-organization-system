import { useState, useEffect } from 'react';
import { X, Clock, FileText, Download, CheckCircle, AlertTriangle, RefreshCw, ChefHat, Info, Heart } from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import { getWeekdayLabel, formatDateShort, getDateRange } from '../../utils/date';
import { getHistoryList, getHistoryDetail, type HistoryRecord } from '../../services/api';

/* ========== 预览完整菜单弹窗 ========== */
export function PreviewModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const { config, weeklyMenu } = useAppStore();
    
    if (!isOpen) return null;
    
    const dates = config ? getDateRange(config.context_overview.schedule.start_date, config.context_overview.schedule.end_date) : [];
    const enabledMeals = config?.meals_config.filter(m => m.enabled) || [];

    return (
        <div className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center backdrop-blur-sm p-8">
            <div className="bg-white w-full max-w-6xl max-h-[90vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
                <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-primary-50">
                    <h2 className="text-lg font-bold text-primary-900 flex items-center gap-2">
                        <FileText size={20} />
                        完整排餐方案预览
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-full transition-colors text-primary-900">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="flex-1 overflow-auto p-6 bg-surface">
                    {weeklyMenu ? (
                        <div className="bg-white rounded-xl border border-border-light shadow-sm overflow-hidden">
                            <table className="w-full border-collapse text-sm">
                                <thead>
                                    <tr className="bg-gray-50 border-b border-border-light">
                                        <th className="px-4 py-3 text-left font-semibold text-text-secondary w-20">餐次</th>
                                        <th className="px-4 py-3 text-left font-semibold text-text-secondary w-24">分类</th>
                                        {dates.map((d) => (
                                            <th key={d} className="px-3 py-3 text-center font-semibold text-text-secondary border-l border-border-light min-w-[120px]">
                                                <div>{getWeekdayLabel(d)}</div>
                                                <div className="text-xs text-text-muted font-normal mt-0.5">{formatDateShort(d)}</div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {enabledMeals.map((meal) =>
                                        meal.dish_structure.categories.map((cat, catIdx) => (
                                            <tr key={`${meal.id}-${catIdx}`} className="border-b border-border-light last:border-0 hover:bg-gray-50/50">
                                                {catIdx === 0 && (
                                                    <td
                                                        rowSpan={meal.dish_structure.categories.length}
                                                        className="px-4 py-3 font-semibold text-text-primary border-r border-border-light bg-gray-50/30 text-center align-middle"
                                                    >
                                                        {meal.meal_name}
                                                    </td>
                                                )}
                                                <td className="px-4 py-3 text-text-secondary border-r border-border-light bg-gray-50/10">
                                                    {cat.name}
                                                </td>
                                                {dates.map((d) => {
                                                    const dishes = weeklyMenu[d]?.[meal.meal_name]?.[cat.name] || [];
                                                    return (
                                                        <td key={d} className="px-3 py-3 border-r border-border-light last:border-0 align-top">
                                                            {dishes.length > 0 ? (
                                                                <div className="space-y-1.5 flex flex-col items-center">
                                                                    {dishes.map((dish, i) => (
                                                                        <div key={i} className="text-center">
                                                                            <span className="font-medium text-text-primary block">{(dish.name || '').replace(/_\d+$/, '')}</span>
                                                                            <span className="text-xs text-text-muted mx-1">¥{Math.round(dish.cost_per_serving || 0)}</span>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            ) : (
                                                                <div className="text-center text-text-muted text-xs opacity-50">—</div>
                                                            )}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="h-64 flex flex-col items-center justify-center text-text-muted">
                            <FileText size={48} className="opacity-20 mb-4" />
                            <p>尚未生成菜单，请先在对话框中让助手为您排菜。</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}


/* ========== 营养与质检报告弹窗 ========== */
export function NutritionModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const { metrics } = useAppStore();
    
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center backdrop-blur-sm p-4">
            <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-down">
                <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-accent-50">
                    <h2 className="text-lg font-bold text-accent-900 flex items-center gap-2">
                        <CheckCircle size={20} />
                        营养与排餐质检报告
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-full transition-colors text-accent-900">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="p-6 space-y-6 bg-surface overflow-auto max-h-[80vh]">
                    {metrics ? (
                        <>
                            {/* 核心分数环 */}
                            <div className="flex bg-white p-5 rounded-2xl border border-border shadow-sm items-center justify-around">
                                <div className="text-center">
                                    <p className="text-sm font-medium text-text-muted mb-1">综合营养评分</p>
                                    <div className="text-4xl font-extrabold text-accent-600">
                                        {metrics.avg_nutrition_score} <span className="text-lg text-accent-400">/100</span>
                                    </div>
                                    <p className="text-xs text-text-secondary mt-2">基于荤素搭配与食材多样性测算</p>
                                </div>
                                <div className="w-px h-20 bg-border"></div>
                                <div className="grid grid-cols-2 gap-x-8 gap-y-4">
                                    <div>
                                        <p className="text-xs text-text-muted">菜品库重复率</p>
                                        <p className="text-lg font-bold text-text-primary">{metrics.repeat_rate}%</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-text-muted">总估测成本</p>
                                        <p className="text-lg font-bold text-text-primary">¥{metrics.total_cost}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-text-muted">合规告警项</p>
                                        <p className={`text-lg font-bold ${metrics.alert_count > 0 ? 'text-red-500' : 'text-green-500'}`}>
                                            {metrics.alert_count} 项
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* 告警与注意事项 */}
                            <div className="bg-white rounded-2xl border border-border shadow-sm overflow-hidden">
                                <div className="px-4 py-3 bg-red-50 border-b border-border">
                                    <h3 className="font-semibold text-red-800 flex items-center gap-1.5 text-sm">
                                        <AlertTriangle size={16} /> 
                                        违规与调整建议
                                    </h3>
                                </div>
                                <div className="p-4">
                                    {metrics.alerts && metrics.alerts.length > 0 ? (
                                        <ul className="space-y-2">
                                            {metrics.alerts.map((alert: string, idx: number) => (
                                                <li key={idx} className="text-sm text-text-secondary flex gap-2">
                                                    <span className="text-red-400">•</span>
                                                    <span>{alert}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <div className="flex items-center gap-2 text-green-600 text-sm py-4 justify-center bg-green-50 rounded-lg">
                                            <CheckCircle size={16} /> 
                                            当前菜单完美符合所有排餐约束条件，表现极佳！
                                        </div>
                                    )}
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="py-12 flex flex-col justify-center items-center text-text-muted">
                            <p>暂无数据，请先生成菜单或等待数据加载。</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ========== 历史记录夹弹窗 ========== */
export function HistoryModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const { setConfig, setWeeklyMenu, setMetrics } = useAppStore();
    const [records, setRecords] = useState<HistoryRecord[]>([]);
    const [loading, setLoading] = useState(false);
    const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            setLoading(true);
            getHistoryList().then(setRecords).finally(() => setLoading(false));
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleApply = async (id: string) => {
        try {
            setLoadingDetailId(id);
            const detail = await getHistoryDetail(id);
            if (detail.menu) {
                setConfig(detail.config);
                setWeeklyMenu(detail.menu);
                setMetrics(detail.metrics);
                onClose();
            }
        } catch (error) {
            alert("读取历史记录失败");
        } finally {
            setLoadingDetailId(null);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center backdrop-blur-sm p-4">
            <div className="bg-white w-full max-w-lg rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
                <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-white">
                    <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
                        <Clock size={20} className="text-primary-500" />
                        历史排餐记录夹
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-full transition-colors text-text-muted">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="flex-1 overflow-auto bg-surface p-4 max-h-[60vh]">
                    {loading ? (
                        <div className="py-10 text-center text-sm text-text-muted flex justify-center items-center gap-2">
                            <RefreshCw size={16} className="animate-spin" /> 加载中...
                        </div>
                    ) : records.length > 0 ? (
                        <div className="space-y-3">
                            {records.map(r => (
                                <div key={r.id} className="bg-white border border-border shadow-sm rounded-xl p-4 flex justify-between items-center transition-all hover:border-primary-300">
                                    <div>
                                        <h3 className="font-semibold text-text-primary text-sm">{r.name}</h3>
                                        <p className="text-xs text-text-muted mt-1">{new Date(r.timestamp).toLocaleString()}</p>
                                        {r.metrics && (
                                            <p className="text-xs text-text-secondary mt-2 flex gap-3">
                                                <span>成本: ¥{r.metrics.total_cost}</span>
                                                <span>营养: {r.metrics.avg_nutrition_score}分</span>
                                            </p>
                                        )}
                                    </div>
                                    <button 
                                        className="px-4 py-2 bg-primary-50 text-primary-600 hover:bg-primary-100 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                                        onClick={() => handleApply(r.id)}
                                        disabled={loadingDetailId === r.id}
                                    >
                                        {loadingDetailId === r.id ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
                                        应用此版
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="py-12 flex flex-col items-center justify-center text-text-muted">
                            <Clock size={40} className="opacity-20 mb-3" />
                            <p className="text-sm">暂无保存的历史记录</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ========== 菜品定量配方弹窗 ========== */
export function RecipeModal({ isOpen, onClose, dish }: { isOpen: boolean; onClose: () => void; dish: any }) {
    if (!isOpen || !dish) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center backdrop-blur-sm p-4">
            <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
                <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-warm-50">
                    <h2 className="text-lg font-bold text-warm-900 flex items-center gap-2">
                        <ChefHat size={20} />
                        菜品定量配方
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-full transition-colors text-warm-900">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="p-6 bg-surface overflow-auto max-h-[70vh]">
                    <div className="mb-6 text-center">
                        <h3 className="text-2xl font-bold text-text-primary">{(dish.name || '').replace(/_\d+$/, '')}</h3>
                        <p className="text-sm text-text-muted mt-1">口味: {dish.flavor || '未知'} | 预估单人成本: ¥{Math.round(dish.cost_per_serving || 0)}</p>
                    </div>

                    {dish.ingredients_quantified && Array.isArray(dish.ingredients_quantified) && dish.ingredients_quantified.length > 0 && (
                        <div className="mb-6 bg-white p-4 rounded-xl border border-border shadow-sm">
                            <h4 className="font-semibold text-sm mb-3 text-text-secondary flex items-center gap-2">
                                <Info size={16} className="text-primary-500" />
                                定量配料标准 (每人份)
                            </h4>
                            <div className="text-sm text-text-primary flex flex-wrap gap-2 mt-2">
                                {(dish.ingredients_quantified as Array<{name: string, category: string, amount_g: number}>).map((ing, i) => (
                                    <span key={i} className="px-2 py-1 bg-surface border border-border-light rounded-md text-xs">
                                        {ing.name} <span className="text-primary-600 font-medium">{ing.amount_g}g</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {dish.nutrition && (
                        <div className="bg-white p-4 rounded-xl border border-border shadow-sm">
                            <h4 className="font-semibold text-sm mb-3 text-text-secondary flex items-center gap-2">
                                <Heart size={16} className="text-red-400" />
                                营养参考 (每单人份)
                            </h4>
                            <div className="grid grid-cols-4 gap-2 text-center text-sm">
                                <div className="bg-orange-50 rounded-lg p-2">
                                    <p className="text-[10px] text-orange-600/70 mb-1">热量</p>
                                    <p className="font-semibold text-orange-700">{dish.nutrition.calories}<span className="text-[10px] font-normal ml-0.5">kcal</span></p>
                                </div>
                                <div className="bg-blue-50 rounded-lg p-2">
                                    <p className="text-[10px] text-blue-600/70 mb-1">蛋白质</p>
                                    <p className="font-semibold text-blue-700">{dish.nutrition.protein}<span className="text-[10px] font-normal ml-0.5">g</span></p>
                                </div>
                                <div className="bg-yellow-50 rounded-lg p-2">
                                    <p className="text-[10px] text-yellow-600/70 mb-1">脂肪</p>
                                    <p className="font-semibold text-yellow-700">{dish.nutrition.fat}<span className="text-[10px] font-normal ml-0.5">g</span></p>
                                </div>
                                <div className="bg-green-50 rounded-lg p-2">
                                    <p className="text-[10px] text-green-600/70 mb-1">碳水</p>
                                    <p className="font-semibold text-green-700">{dish.nutrition.carbs}<span className="text-[10px] font-normal ml-0.5">g</span></p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
