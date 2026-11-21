from sqlalchemy import BigInteger, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Campaign(TimestampMixin, Base):
    """Local record of campaigns created through Keitaro Manager.

    Keitaro stays the source of truth; this table keeps the creation parameters for history/audit.
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("length(country) = 2", name="country_iso2"),
        CheckConstraint("offer_id > 0", name="offer_id_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    offer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    domain_id: Mapped[int | None] = mapped_column(BigInteger)
    group_id: Mapped[int | None] = mapped_column(BigInteger)
    traffic_source_id: Mapped[int | None] = mapped_column(BigInteger)
    geo_stream_id: Mapped[int | None] = mapped_column(BigInteger)
    offer_stream_id: Mapped[int | None] = mapped_column(BigInteger)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
