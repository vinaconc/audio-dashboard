from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    error = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    lyrics = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    structure_user = Column(JSONB)
    structure_user_saved_at = Column(DateTime)