"""许可证服务 ORM 模型（SQLite / PostgreSQL）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    max_activations: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    devices: Mapped[List["Device"]] = relationship(back_populates="license")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("license_id", "fingerprint", name="uq_license_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    device_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    license: Mapped["License"] = relationship(back_populates="devices")
