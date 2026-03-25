/* ========== 深度规则配置抽屉 (Config Drawer) ========== */
import { useState, useEffect } from 'react';
import {
    X,
    ChevronDown,
    ChevronRight,
    Plus,
    Trash2,
    Save,
    AlertTriangle,
} from 'lucide-react';
import { useAppStore } from '../../stores/app-store';
import type { KitchenClass, DiningStyleType, MealConfig, DishCategory } from '../../types';
import { getDishCategories } from '../../services/api';

const KITCHEN_CLASS_OPTIONS: KitchenClass[] = ['一类灶', '二类灶', '三类灶'];
const DINING_STYLES: DiningStyleType[] = ['固定餐标', '自选打菜', '自助餐', '多套餐模式'];
const STAPLE_OPTIONS = ['米饭', '炒饭', '面食', '包子', '饺子', '馒头', '花卷'];

export default function ConfigDrawer() {
    const {
        config,
        configDrawerOpen,
        setConfigDrawerOpen,
        updateKitchenClass,
        updateCity,
        updateSchedule,
        updateMealConfig,
        toggleMeal,
        addMeal,
        removeMeal,
        updateRedLines,
    } = useAppStore();

    const [expandedMeals, setExpandedMeals] = useState<Set<string>>(new Set());
    const [newMealName, setNewMealName] = useState('');
    const [redLineInput, setRedLineInput] = useState(config.global_hard_constraints.red_lines.join('\n'));
    const [availableCategories, setAvailableCategories] = useState<string[]>([]);
    const [addingCategoryToMealId, setAddingCategoryToMealId] = useState<string | null>(null);
    const [newHealthCondition, setNewHealthCondition] = useState('');
    const [isAddingHealth, setIsAddingHealth] = useState(false);
    const [newDietaryRestriction, setNewDietaryRestriction] = useState('');
    const [isAddingDietary, setIsAddingDietary] = useState(false);

    useEffect(() => {
        getDishCategories().then(setAvailableCategories);
    }, []);

    const toggleExpand = (mealId: string) => {
        const next = new Set(expandedMeals);
        next.has(mealId) ? next.delete(mealId) : next.add(mealId);
        setExpandedMeals(next);
    };

    const handleAddCategoryClick = (mealId: string) => {
        setAddingCategoryToMealId(mealId);
    };

    const handleSelectCategory = (mealId: string, meal: MealConfig, name: string) => {
        if (!name) return;
        updateMealConfig(mealId, {
            dish_structure: {
                categories: [...meal.dish_structure.categories, { name, count: 1 }],
            },
        });
        setAddingCategoryToMealId(null);
    };

    const handleRemoveCategory = (mealId: string, meal: MealConfig, catIndex: number) => {
        updateMealConfig(mealId, {
            dish_structure: {
                categories: meal.dish_structure.categories.filter((_, i) => i !== catIndex),
            },
        });
    };

    const handleCategoryChange = (mealId: string, meal: MealConfig, catIndex: number, updates: Partial<DishCategory>) => {
        updateMealConfig(mealId, {
            dish_structure: {
                categories: meal.dish_structure.categories.map((c, i) =>
                    i === catIndex ? { ...c, ...updates } : c
                ),
            },
        });
    };

    const handleSave = () => {
        updateRedLines(redLineInput.split('\n').filter(Boolean));
        setConfigDrawerOpen(false);
    };

    if (!configDrawerOpen) return null;

    return (
        <>
            {/* 遮罩层 */}
            <div
                className="fixed inset-0 bg-black/20 z-40 backdrop-blur-sm animate-fade-in"
                onClick={() => setConfigDrawerOpen(false)}
            />

            {/* 抽屉面板 */}
            <div className="fixed right-0 top-0 h-full w-[480px] max-w-[90vw] bg-white z-50 shadow-2xl animate-slide-right overflow-hidden flex flex-col">
                {/* 头部 */}
                <div className="px-5 py-4 border-b border-border-light flex items-center justify-between bg-gradient-to-r from-primary-50 to-accent-50">
                    <div>
                        <h2 className="text-base font-bold text-text-primary">深度规则配置</h2>
                        <p className="text-[11px] text-text-muted mt-0.5">配置结构化约束，供校验 Agent 进行强约束拦截</p>
                    </div>
                    <button onClick={() => setConfigDrawerOpen(false)} className="w-8 h-8 rounded-lg hover:bg-white/60 flex items-center justify-center">
                        <X size={16} className="text-text-secondary" />
                    </button>
                </div>

                {/* 内容区域 */}
                <div className="flex-1 overflow-y-auto p-5 space-y-5">
                    {/* === 3.3.1 基础属性 === */}
                    <section>
                        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">基础属性</h3>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs text-text-muted mb-1">灶别标准</label>
                                <select
                                    value={config.context_overview.kitchen_class}
                                    onChange={(e) => updateKitchenClass(e.target.value as KitchenClass)}
                                    className="w-full px-3 py-2 rounded-lg border border-border text-sm bg-surface focus:border-primary-400 outline-none"
                                >
                                    {KITCHEN_CLASS_OPTIONS.map((s) => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs text-text-muted mb-1">所属支队</label>
                                <input
                                    type="text"
                                    value={config.context_overview.city}
                                    onChange={(e) => updateCity(e.target.value)}
                                    className="w-full px-3 py-2 rounded-lg border border-border text-sm bg-surface focus:border-primary-400 outline-none"
                                    placeholder="输入支队名称"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 mt-3">
                            <div>
                                <label className="block text-xs text-text-muted mb-1">起始日期</label>
                                <input
                                    type="date"
                                    value={config.context_overview.schedule.start_date}
                                    onChange={(e) => updateSchedule(e.target.value, config.context_overview.schedule.end_date)}
                                    className="w-full px-3 py-2 rounded-lg border border-border text-sm bg-surface focus:border-primary-400 outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-text-muted mb-1">结束日期</label>
                                <input
                                    type="date"
                                    value={config.context_overview.schedule.end_date}
                                    onChange={(e) => updateSchedule(config.context_overview.schedule.start_date, e.target.value)}
                                    className="w-full px-3 py-2 rounded-lg border border-border text-sm bg-surface focus:border-primary-400 outline-none"
                                />
                            </div>
                        </div>
                    </section>

                    <hr className="border-border-light" />

                    {/* === 3.3.2 餐次配置 === */}
                    <section>
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">包含的餐次</h3>
                            <div className="flex items-center gap-1">
                                <input
                                    type="text"
                                    value={newMealName}
                                    onChange={(e) => setNewMealName(e.target.value)}
                                    placeholder="新餐次名称"
                                    className="w-24 px-2 py-1 text-xs border border-border rounded-md outline-none focus:border-primary-400"
                                />
                                <button
                                    onClick={() => {
                                        if (newMealName.trim()) {
                                            addMeal(newMealName.trim());
                                            setNewMealName('');
                                        }
                                    }}
                                    className="w-6 h-6 rounded-md bg-primary-500 text-white flex items-center justify-center hover:bg-primary-600"
                                >
                                    <Plus size={12} />
                                </button>
                            </div>
                        </div>

                        <div className="space-y-2">
                            {config.meals_config.map((meal) => (
                                <div key={meal.id} className="border border-border-light rounded-xl overflow-hidden">
                                    {/* 餐次标题行 */}
                                    <div
                                        className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer transition-colors ${meal.enabled ? 'bg-primary-50/50' : 'bg-gray-50'
                                            }`}
                                        onClick={() => toggleExpand(meal.id)}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={meal.enabled}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                toggleMeal(meal.id);
                                            }}
                                            className="accent-primary-500"
                                        />
                                        <span className="text-sm font-medium flex-1">{meal.meal_name}</span>
                                        {meal.enabled && (
                                            <span className="text-[10px] text-text-muted">
                                                {meal.diners_count}人 · ¥{meal.budget_per_person}/人
                                            </span>
                                        )}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removeMeal(meal.id);
                                            }}
                                            className="w-5 h-5 rounded hover:bg-red-100 flex items-center justify-center"
                                        >
                                            <Trash2 size={11} className="text-red-400" />
                                        </button>
                                        {expandedMeals.has(meal.id) ? (
                                            <ChevronDown size={14} className="text-text-muted" />
                                        ) : (
                                            <ChevronRight size={14} className="text-text-muted" />
                                        )}
                                    </div>

                                    {/* === 3.3.3 餐次内部详细配置 === */}
                                    {expandedMeals.has(meal.id) && meal.enabled && (
                                        <div className="px-4 py-3 space-y-4 bg-white border-t border-border-light">
                                            {/* 基础指标 */}
                                            <div className="grid grid-cols-3 gap-3">
                                                <div>
                                                    <label className="block text-[11px] text-text-muted mb-1">就餐人数</label>
                                                    <input
                                                        type="number"
                                                        value={meal.diners_count}
                                                        onChange={(e) => updateMealConfig(meal.id, { diners_count: Number(e.target.value) })}
                                                        className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-[11px] text-text-muted mb-1">入口率(%)</label>
                                                    <input
                                                        type="number"
                                                        value={meal.intake_rate}
                                                        onChange={(e) => updateMealConfig(meal.id, { intake_rate: Number(e.target.value) })}
                                                        className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-[11px] text-text-muted mb-1">餐标(元/人)</label>
                                                    <input
                                                        type="number"
                                                        value={meal.budget_per_person}
                                                        onChange={(e) => updateMealConfig(meal.id, { budget_per_person: Number(e.target.value) })}
                                                        className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                    />
                                                </div>
                                            </div>

                                            {/* 用餐方式 */}
                                            <div>
                                                <label className="block text-[11px] text-text-muted mb-1">用餐方式</label>
                                                <select
                                                    value={meal.dining_style.type}
                                                    onChange={(e) =>
                                                        updateMealConfig(meal.id, {
                                                            dining_style: { ...meal.dining_style, type: e.target.value as DiningStyleType },
                                                        })
                                                    }
                                                    className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                >
                                                    {DINING_STYLES.map((ds) => (
                                                        <option key={ds} value={ds}>{ds}</option>
                                                    ))}
                                                </select>
                                            </div>

                                            {/* 菜品分类栅格 */}
                                            <div>
                                                <div className="flex items-center justify-between mb-2">
                                                    <label className="text-[11px] text-text-muted font-medium">菜品种类结构</label>
                                                    <button
                                                        onClick={() => handleAddCategoryClick(meal.id)}
                                                        className="text-[10px] text-primary-500 hover:text-primary-600 flex items-center gap-0.5"
                                                    >
                                                        <Plus size={10} /> 加分类
                                                    </button>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {meal.dish_structure.categories.map((cat, i) => (
                                                        <div key={i} className="flex items-center gap-1 px-2 py-1.5 bg-surface rounded-lg border border-border-light group">
                                                            <span className="text-xs font-medium text-text-primary px-1">{cat.name}</span>
                                                            <span className="text-[10px] text-text-muted">×</span>
                                                            <input
                                                                type="number"
                                                                value={cat.count}
                                                                onChange={(e) => handleCategoryChange(meal.id, meal, i, { count: Number(e.target.value) })}
                                                                className="w-8 text-xs bg-transparent outline-none text-center"
                                                                min={0}
                                                            />
                                                            <button
                                                                onClick={() => handleRemoveCategory(meal.id, meal, i)}
                                                                className="w-4 h-4 rounded hover:bg-red-100 items-center justify-center hidden group-hover:flex"
                                                            >
                                                                <X size={8} className="text-red-400" />
                                                            </button>
                                                        </div>
                                                    ))}

                                                    {addingCategoryToMealId === meal.id && (
                                                        <div className="flex items-center gap-1 px-2 py-1 bg-primary-50 rounded-lg border border-primary-100 animate-pulse-subtle">
                                                            <select
                                                                autoFocus
                                                                className="text-xs bg-transparent outline-none cursor-pointer py-1"
                                                                onChange={(e) => handleSelectCategory(meal.id, meal, e.target.value)}
                                                                onBlur={() => setAddingCategoryToMealId(null)}
                                                                defaultValue=""
                                                            >
                                                                <option value="" disabled>选择分类...</option>
                                                                {availableCategories
                                                                    .filter(ac => !meal.dish_structure.categories.some(c => c.name === ac))
                                                                    .map(ac => (
                                                                        <option key={ac} value={ac}>{ac}</option>
                                                                    ))
                                                                }
                                                            </select>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* 主食类型 */}
                                            <div>
                                                <label className="block text-[11px] text-text-muted mb-1.5">主食细类要求</label>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {STAPLE_OPTIONS.map((st) => (
                                                        <button
                                                            key={st}
                                                            onClick={() => {
                                                                const next = meal.staple_types.includes(st)
                                                                    ? meal.staple_types.filter((t) => t !== st)
                                                                    : [...meal.staple_types, st];
                                                                updateMealConfig(meal.id, { staple_types: next });
                                                            }}
                                                            className={`px-2 py-1 text-[11px] rounded-md border transition-colors ${meal.staple_types.includes(st)
                                                                    ? 'bg-primary-500 text-white border-primary-500'
                                                                    : 'border-border text-text-secondary hover:border-primary-300'
                                                                }`}
                                                        >
                                                            {st}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* 汤品要求 */}
                                            <div>
                                                <label className="block text-[11px] text-text-muted mb-1">汤品描述</label>
                                                <input
                                                    type="text"
                                                    value={meal.soup_requirements.description}
                                                    onChange={(e) =>
                                                        updateMealConfig(meal.id, {
                                                            soup_requirements: { ...meal.soup_requirements, description: e.target.value },
                                                        })
                                                    }
                                                    className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                    placeholder="如：需包含1款老火例汤"
                                                />
                                            </div>

                                            {/* 口味偏好 */}
                                            <div>
                                                <label className="block text-[11px] text-text-muted mb-1">特殊口味偏好</label>
                                                <input
                                                    type="text"
                                                    value={meal.flavor_preferences}
                                                    onChange={(e) => updateMealConfig(meal.id, { flavor_preferences: e.target.value })}
                                                    className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                    placeholder="如：少盐少油、偏甜口、重口味下饭"
                                                />
                                            </div>

                                            {/* 必用食材 / 必排菜品 */}
                                            <div className="grid grid-cols-2 gap-3">
                                                <div>
                                                    <label className="block text-[11px] text-text-muted mb-1">必用食材</label>
                                                    <input
                                                        type="text"
                                                        value={meal.meal_specific_constraints.required_ingredients.join(', ')}
                                                        onChange={(e) =>
                                                            updateMealConfig(meal.id, {
                                                                meal_specific_constraints: {
                                                                    ...meal.meal_specific_constraints,
                                                                    required_ingredients: e.target.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
                                                                },
                                                            })
                                                        }
                                                        className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                        placeholder="逗号分隔，如：土豆, 瘦肉"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-[11px] text-text-muted mb-1">必排菜品</label>
                                                    <input
                                                        type="text"
                                                        value={meal.meal_specific_constraints.mandatory_dishes.join(', ')}
                                                        onChange={(e) =>
                                                            updateMealConfig(meal.id, {
                                                                meal_specific_constraints: {
                                                                    ...meal.meal_specific_constraints,
                                                                    mandatory_dishes: e.target.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
                                                                },
                                                            })
                                                        }
                                                        className="w-full px-2 py-1.5 rounded-md border border-border text-xs outline-none focus:border-primary-400"
                                                        placeholder="如：周三: 红烧肉"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>

                    <hr className="border-border-light" />

                    {/* === 3.3.4 特殊人群与红线 === */}
                    <section>
                        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">特殊人群 · 健康状态</h3>
                        <div className="flex flex-wrap gap-2">
                            {config.global_hard_constraints.health_conditions.map((hc, i) => (
                                <label key={i} className="flex items-center gap-1.5 px-2 py-1 bg-surface rounded-lg border border-border-light text-xs cursor-pointer hover:border-primary-300">
                                    <input
                                        type="checkbox"
                                        checked={hc.enabled}
                                        onChange={() => {
                                            const next = [...config.global_hard_constraints.health_conditions];
                                            next[i] = { ...next[i], enabled: !next[i].enabled };
                                            useAppStore.setState((s) => ({
                                                config: {
                                                    ...s.config,
                                                    global_hard_constraints: { ...s.config.global_hard_constraints, health_conditions: next },
                                                },
                                            }));
                                        }}
                                        className="accent-primary-500"
                                    />
                                    <span>{hc.condition}</span>
                                </label>
                            ))}
                            {isAddingHealth ? (
                                <div className="flex items-center gap-1 animate-in fade-in zoom-in duration-200">
                                    <input
                                        type="text"
                                        value={newHealthCondition}
                                        onChange={(e) => setNewHealthCondition(e.target.value)}
                                        className="w-20 px-2 py-1 text-xs border border-primary-300 rounded-md outline-none"
                                        placeholder="新状态"
                                        autoFocus
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                if (newHealthCondition.trim()) {
                                                    const next = [...config.global_hard_constraints.health_conditions, { condition: newHealthCondition.trim(), count: 0, enabled: true }];
                                                    useAppStore.setState((s) => ({
                                                        config: {
                                                            ...s.config,
                                                            global_hard_constraints: { ...s.config.global_hard_constraints, health_conditions: next },
                                                        },
                                                    }));
                                                    setNewHealthCondition('');
                                                }
                                                setIsAddingHealth(false);
                                            } else if (e.key === 'Escape') {
                                                setIsAddingHealth(false);
                                            }
                                        }}
                                        onBlur={() => {
                                            if (!newHealthCondition.trim()) setIsAddingHealth(false);
                                        }}
                                    />
                                </div>
                            ) : (
                                <button
                                    onClick={() => setIsAddingHealth(true)}
                                    className="flex items-center gap-1 px-2 py-1 border border-dashed border-border-light rounded-lg text-[10px] text-text-muted hover:border-primary-300 hover:text-primary-500 transition-colors"
                                >
                                    <Plus size={10} /> 自定义
                                </button>
                            )}
                        </div>
                    </section>

                    <section>
                        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">饮食禁忌群体</h3>
                        <div className="flex flex-wrap gap-2">
                            {config.global_hard_constraints.dietary_restrictions.map((dr, i) => (
                                <label key={i} className="flex items-center gap-1.5 px-2 py-1 bg-surface rounded-lg border border-border-light text-xs cursor-pointer hover:border-primary-300">
                                    <input
                                        type="checkbox"
                                        checked={dr.enabled}
                                        onChange={() => {
                                            const next = [...config.global_hard_constraints.dietary_restrictions];
                                            next[i] = { ...next[i], enabled: !next[i].enabled };
                                            useAppStore.setState((s) => ({
                                                config: {
                                                    ...s.config,
                                                    global_hard_constraints: { ...s.config.global_hard_constraints, dietary_restrictions: next },
                                                },
                                            }));
                                        }}
                                        className="accent-primary-500"
                                    />
                                    <span>{dr.restriction}</span>
                                </label>
                            ))}
                            {isAddingDietary ? (
                                <div className="flex items-center gap-1 animate-in fade-in zoom-in duration-200">
                                    <input
                                        type="text"
                                        value={newDietaryRestriction}
                                        onChange={(e) => setNewDietaryRestriction(e.target.value)}
                                        className="w-20 px-2 py-1 text-xs border border-primary-300 rounded-md outline-none"
                                        placeholder="新禁忌"
                                        autoFocus
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                if (newDietaryRestriction.trim()) {
                                                    const next = [...config.global_hard_constraints.dietary_restrictions, { restriction: newDietaryRestriction.trim(), count: 0, enabled: true }];
                                                    useAppStore.setState((s) => ({
                                                        config: {
                                                            ...s.config,
                                                            global_hard_constraints: { ...s.config.global_hard_constraints, dietary_restrictions: next },
                                                        },
                                                    }));
                                                    setNewDietaryRestriction('');
                                                }
                                                setIsAddingDietary(false);
                                            } else if (e.key === 'Escape') {
                                                setIsAddingDietary(false);
                                            }
                                        }}
                                        onBlur={() => {
                                            if (!newDietaryRestriction.trim()) setIsAddingDietary(false);
                                        }}
                                    />
                                </div>
                            ) : (
                                <button
                                    onClick={() => setIsAddingDietary(true)}
                                    className="flex items-center gap-1 px-2 py-1 border border-dashed border-border-light rounded-lg text-[10px] text-text-muted hover:border-primary-300 hover:text-primary-500 transition-colors"
                                >
                                    <Plus size={10} /> 自定义
                                </button>
                            )}
                        </div>
                    </section>

                    <section>
                        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                            <AlertTriangle size={12} className="text-red-400" />
                            全局绝对红线
                        </h3>
                        <textarea
                            value={redLineInput}
                            onChange={(e) => setRedLineInput(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-red-200 text-xs outline-none focus:border-red-400 bg-red-50/30 min-h-[60px] resize-none"
                            placeholder="每行输入一种禁止食材，如：&#10;花生&#10;海鲜"
                            rows={3}
                        />
                    </section>
                </div>

                {/* 底部操作 */}
                <div className="px-5 py-4 border-t border-border-light bg-surface flex gap-3">
                    <button
                        onClick={() => setConfigDrawerOpen(false)}
                        className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-secondary hover:bg-gray-50 transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleSave}
                        className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 text-white text-sm font-medium flex items-center justify-center gap-1.5 hover:shadow-md transition-all"
                    >
                        <Save size={14} />
                        保存并同步
                    </button>
                </div>
            </div>
        </>
    );
}
