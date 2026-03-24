"""
菜品模型
"""
from sqlalchemy import Column, Integer, String, Float, JSON
from ..database import Base

class Dish(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    # ingredients_quantified: [{"name": "大米", "category": "大米", "amount_g": 150}]
    ingredients_quantified = Column(JSON, nullable=False, default=list) 
    # applicable_meals: ["早餐", "午餐", "晚餐", "夜宵", "其他"]
    applicable_meals = Column(JSON, nullable=False, default=list)
    flavor = Column(String(100), nullable=False)
    cost_per_serving = Column(Float, nullable=False)
    nutrition = Column(JSON, nullable=False) # dict: calories, protein, carbs, fat
    tags = Column(JSON, nullable=False) # list of str
