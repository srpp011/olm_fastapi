import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from database import Base

class Layer(Base):
    __tablename__ = 'layers'

    id = Column(Integer, primary_key=True, index=True)
    request_date = Column(DateTime, default=datetime.datetime.utcnow)
    name = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)