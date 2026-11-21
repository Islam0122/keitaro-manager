from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

PASSWORD_MIN_LENGTH = 10


def check_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов")
    if value.strip() != value:
        raise ValueError("Пароль не должен начинаться или заканчиваться пробелом")
    if value.isdigit() or value.isalpha():
        raise ValueError("Пароль должен содержать и буквы, и цифры/символы")
    return value


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool
    last_login_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(max_length=256)

    _strength = field_validator("new_password")(check_password_strength)
