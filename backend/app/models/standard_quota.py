"""
主副食、燃料定量标准模型
"""
from sqlalchemy import Column, Integer, String, JSON
from ..database import Base

class StandardQuota(Base):
    __tablename__ = "standard_quotas"

    id = Column(Integer, primary_key=True, index=True)
    # class_type: "一类灶", "二类灶", "三类灶"
    class_type = Column(String(50), nullable=False, unique=True, index=True)
    # quotas: {"大米": 420, "面粉": 180, "畜肉": 180, "禽肉": 60, ...}
    quotas = Column(JSON, nullable=False)
