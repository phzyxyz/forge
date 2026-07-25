"""SELECT FOR UPDATE SQL emission."""

from __future__ import annotations

import pytest
from phzyx.orm import Field, Model
from phzyx.orm.sql import build_select
from phzyx.schema.types import Dialect


class Row(Model):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field()

    class Meta:
        table = "rows_fu"
        register = False


@pytest.mark.unit
def test_for_update_sql() -> None:
    frag = build_select(Row, dialect=Dialect.POSTGRES, for_update=True, limit=1)
    assert "FOR UPDATE" in frag.sql
    frag2 = build_select(Row, dialect=Dialect.POSTGRES, for_update="SKIP LOCKED")
    assert "SKIP LOCKED" in frag2.sql
