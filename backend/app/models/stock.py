from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class WatchlistItem(Base):
    __tablename__ = 'watchlist'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(50), nullable=False)
    market = Column(String(10), nullable=False)
    added_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

class AnalysisCache(Base):
    __tablename__ = 'analysis_cache'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(50))
    analysis_type = Column(String(20), default='comprehensive')
    user_message = Column(Text, default='')
    content = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class InvestmentSummary(Base):
    __tablename__ = 'investment_summaries'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(50))
    summary = Column(Text, nullable=False)
    source_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

class ChatThread(Base):
    __tablename__ = 'chat_threads'
    id = Column(String(36), primary_key=True)
    title = Column(String(100), default='')
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    stock_code = Column(String(20), default='')
    stock_name = Column(String(50), default='')
    stock_data = Column(Text, default='')
    created_at = Column(DateTime, server_default=func.now())

class Portfolio(Base):
    __tablename__ = 'portfolios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), default='默认持仓')
    image_path = Column(String(200), default='')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    items = relationship('PortfolioItem', backref='portfolio', cascade='all, delete-orphan')

class PortfolioItem(Base):
    __tablename__ = 'portfolio_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(50), nullable=False)
    asset_type = Column(String(20), default='fund')
    quantity = Column(Float, default=0)
    cost_price = Column(Float, default=0)
    current_price = Column(Float, default=0)
    holding_amount = Column(Float, default=0)
    cost_amount = Column(Float, default=0)
    holding_return = Column(Float, default=0)
    daily_return = Column(Float, default=0)
    daily_return_pct = Column(Float, default=0)
    sector = Column(String(50), default='')
    created_at = Column(DateTime, server_default=func.now())
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(50), default='')
    avatar = Column(String(200), default='')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    investment_style = Column(String(20), default='medium_term')  # short_term / medium_term / long_term
    risk_preference = Column(String(20), default='moderate')      # conservative / moderate / aggressive
    focus_industries = Column(String(200), default='')            # Comma-separated industry names
    focus_stocks = Column(String(200), default='')                # Comma-separated stock codes
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
