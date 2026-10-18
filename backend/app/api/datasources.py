import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.errors import AppError, not_found
from app.models import Datasource
from app.schemas.api import DatasourceCreate, DatasourceOut
from app.schemas.schema_snapshot import SchemaSnapshot
from app.services import datasources as service
from app.services.indexer import get_indexer
from app.services.target_db import target_pools

router = APIRouter(prefix="/datasources", tags=["datasources"])


def to_out(datasource: Datasource) -> DatasourceOut:
    out = DatasourceOut.model_validate(datasource)
    out.tables_count = service.tables_count(datasource)
    return out


async def get_or_404(db: DbSession, datasource_id: uuid.UUID) -> Datasource:
    datasource = await db.get(Datasource, datasource_id)
    if datasource is None:
        raise not_found("datasource")
    return datasource


@router.get("")
async def list_datasources(db: DbSession, _: CurrentUser) -> list[DatasourceOut]:
    rows = await db.scalars(select(Datasource).order_by(Datasource.created_at))
    return [to_out(d) for d in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_datasource(
    body: DatasourceCreate, db: DbSession, user: AdminUser
) -> DatasourceOut:
    """Подключение принимается, только если роль не может ничего изменить в БД."""
    datasource = await service.create_datasource(db, user.id, body.name, body.connection_url)
    service.schedule_indexing(datasource.id)
    return to_out(datasource)


@router.get("/{datasource_id}/schema")
async def get_schema(datasource_id: uuid.UUID, db: DbSession, _: CurrentUser) -> SchemaSnapshot:
    datasource = await get_or_404(db, datasource_id)
    if datasource.schema_snapshot is None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "schema_not_ready",
            f"Схема ещё не загружена (статус: {datasource.status})",
        )
    return SchemaSnapshot.model_validate(datasource.schema_snapshot)


@router.post("/{datasource_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex(datasource_id: uuid.UUID, db: DbSession, _: AdminUser) -> DatasourceOut:
    datasource = await get_or_404(db, datasource_id)
    service.schedule_indexing(datasource.id)
    return to_out(datasource)


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(datasource_id: uuid.UUID, db: DbSession, _: AdminUser) -> Response:
    datasource = await get_or_404(db, datasource_id)
    await db.delete(datasource)
    await db.commit()
    await target_pools.close(datasource_id)
    await get_indexer().delete(str(datasource_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
