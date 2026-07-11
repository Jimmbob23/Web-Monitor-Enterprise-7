from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="user")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    sites = relationship("Site", back_populates="folder")

class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text)
    tags_csv: Mapped[str] = mapped_column(Text, default="")
    schedule_type: Mapped[str] = mapped_column(String(20), default="interval")
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    cron_expression: Mapped[str] = mapped_column(String(100), default="")
    threshold_percent: Mapped[float] = mapped_column(Float, default=0.5)
    wait_seconds: Mapped[int] = mapped_column(Integer, default=2)
    viewport_width: Mapped[int] = mapped_column(Integer, default=1440)
    viewport_height: Mapped[int] = mapped_column(Integer, default=1200)
    ignore_selectors: Mapped[str] = mapped_column(Text, default="")
    cookie_mode: Mapped[str] = mapped_column(String(30), default="auto")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    baseline_path: Mapped[str] = mapped_column(Text, default="")
    last_status: Mapped[str] = mapped_column(String(50), default="never")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    last_http_status: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="sites")
    changes = relationship("Change", back_populates="site", cascade="all, delete-orphan")
    macro_actions = relationship("MacroAction", back_populates="site", cascade="all, delete-orphan", order_by="MacroAction.position")

class MacroAction(Base):
    __tablename__ = "macro_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    action_type: Mapped[str] = mapped_column(String(40))
    selector_type: Mapped[str] = mapped_column(String(30), default="label")
    selector: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[str] = mapped_column(Text, default="")
    timeout_ms: Mapped[int] = mapped_column(Integer, default=5000)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    site = relationship("Site", back_populates="macro_actions")

class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(50), default="ok")
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    difference_percent: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int] = mapped_column(Integer, default=0)
    screenshot_path: Mapped[str] = mapped_column(Text, default="")
    diff_path: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    site = relationship("Site", back_populates="changes")

class BackupEntry(Base):
    __tablename__ = "backup_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
