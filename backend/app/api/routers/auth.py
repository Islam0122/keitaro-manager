from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import LoginIn, PasswordChangeIn, TokenOut, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut, summary="Вход: получить access token")
async def login(data: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    return await AuthService(session).login(data.username, data.password, ip)


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Сменить пароль")
async def change_password(data: PasswordChangeIn, user: CurrentUser, session: SessionDep) -> Response:
    await AuthService(session).change_password(user, data.current_password, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
