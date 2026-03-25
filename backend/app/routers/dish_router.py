"""
走云智能排菜系统 — 菜品路由

处理 /api/dishes/* 相关请求。
"""
from fastapi import APIRouter
from sqlalchemy import select
from ..services.data_enrichment import search_dishes
from ..database import AsyncSessionLocal
from ..models.dish import Dish

router = APIRouter(prefix="/api/dishes", tags=["菜品库"])

@router.get("/search")
async def dishes_search(q: str = ""):
    """搜索菜品库"""
    if not q.strip():
        return []
    return await search_dishes(q.strip())

@router.get("/library")
async def dishes_library():
    """获取完整菜品库"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Dish))
        dishes = result.scalars().all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "category": d.category,
                "ingredients_quantified": d.ingredients_quantified,
                "applicable_meals": d.applicable_meals,
                "flavor": d.flavor,
                "cost_per_serving": d.cost_per_serving,
                "nutrition": d.nutrition,
                "tags": d.tags,
            } for d in dishes
        ]

@router.get("/categories")
async def dishes_categories():
    """获取菜品库中所有不重复的分类列表"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Dish.category).distinct())
        categories = [row[0] for row in result.all() if row[0]]
        return sorted(categories)
