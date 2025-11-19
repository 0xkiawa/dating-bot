from sqlalchemy import BigInteger, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class ReferalModel(BaseModel):
    __tablename__ = "referals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # Changed from BigInteger
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    inviter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(10), nullable=True, server_default="usr")
    source: Mapped[str] = mapped_column(String(100), nullable=True, server_default="Telegram user")