"""Снимок схемы подключённой БД (CONTRACTS §4)."""

from datetime import datetime

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    comment: str | None = None
    is_pk: bool = False
    fk: str | None = None  # "schema.table.column"
    sample_values: list[str] | None = None


class TableInfo(BaseModel):
    schema_name: str
    name: str
    comment: str | None = None
    row_estimate: int
    columns: list[ColumnInfo]


class SchemaSnapshot(BaseModel):
    datasource_id: str
    timezone: str | None = None
    tables: list[TableInfo]
    created_at: datetime
