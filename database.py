from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# URL_DATABSE = 'postgresql://openlandmap:openlandmap@localhost:5434/stats'
URL_DATABSE = 'postgresql://fastapi:openlandmap@stats_db:5432/stats'

engine = create_engine(URL_DATABSE)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()