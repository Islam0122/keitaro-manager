from fastapi import APIRouter, Response, status

from app.api.deps import KeitaroDep, SessionDep
from app.schemas.keitaro import StreamOut
from app.schemas.stream import StreamIn
from app.services.stream_service import StreamService

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("/{stream_id}", response_model=StreamOut, summary="Поток")
async def get_stream(stream_id: int, keitaro: KeitaroDep, session: SessionDep) -> StreamOut:
    return await StreamService(keitaro[0], session).get(stream_id)


@router.put("/{stream_id}", response_model=StreamOut, summary="Обновить поток")
async def update_stream(stream_id: int, data: StreamIn, keitaro: KeitaroDep, session: SessionDep) -> StreamOut:
    return await StreamService(keitaro[0], session).update(stream_id, data)


@router.post("/{stream_id}/enable", response_model=StreamOut, summary="Включить поток")
async def enable_stream(stream_id: int, keitaro: KeitaroDep, session: SessionDep) -> StreamOut:
    return await StreamService(keitaro[0], session).set_state(stream_id, True)


@router.post("/{stream_id}/disable", response_model=StreamOut, summary="Выключить поток")
async def disable_stream(stream_id: int, keitaro: KeitaroDep, session: SessionDep) -> StreamOut:
    return await StreamService(keitaro[0], session).set_state(stream_id, False)


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить поток")
async def delete_stream(stream_id: int, keitaro: KeitaroDep, session: SessionDep) -> Response:
    await StreamService(keitaro[0], session).delete(stream_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
