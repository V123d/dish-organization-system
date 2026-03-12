"""
走云智能排菜系统 — 菜品路由

处理 /api/dishes/* 相关请求。
"""
from fastapi import APIRouter
from ..services.data_enrichment import search_dishes, DISH_LIBRARY

router = APIRouter(prefix="/api/dishes", tags=["菜品库"])


@router.get("/search")
async def dishes_search(q: str = ""):
    """搜索菜品库"""
    if not q.strip():
        return []
    return search_dishes(q.strip())


@router.get("/library")
async def dishes_library():
    """获取完整菜品库"""
    return DISH_LIBRARY
