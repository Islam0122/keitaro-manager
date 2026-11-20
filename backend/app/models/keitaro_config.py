from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class KeitaroConfig(TimestampMixin, Base):
    """Single-row table with the Keitaro connection and application settings."""

    __tablename__ = "keitaro_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_url: Mapped[str | None] = mapped_column(String(512))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    timeout: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    default_safe_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="https://www.google.com")
