# phzyx-engine

**Not a separate PyPI project** — ships inside **`phzyx-forge`**. Use `uv add 'phzyx-forge[sqlite]'`.


Failsafe schema engine: introspect · diff · push · migrate.

```bash
uv add 'phzyx-forge[sqlite]'
# CLI ships with phzyx-forge
# optional live MySQL/MariaDB (MariaDB DSN aliases to mysql for now):
#   uv add pymysql
#   # or: uv add 'phzyx-engine[mysql]'
```

## Library

```python
from phzyx.engine import connect, push_schema, build_plan
from phzyx.schema import Field, Model, build_manifest

class User(Model):
    id: int = Field(primary_key=True)
    email: str = Field()

    class Meta:
        table = "users"

conn, adapter = connect("sqlite:///:memory:")
push_schema([User], conn, adapter, yes=True)
```

## CLI

```bash
export PHZYX_DATABASE_URL=sqlite:///./dev.db
phzyx db status
phzyx db push --models myapp.models:MODELS --dry-run
phzyx db push --models myapp.models:MODELS --yes
phzyx migrate create --models myapp.models:MODELS -m "init"
phzyx migrate apply
phzyx migrate status
```

See [docs/push-vs-migrate.md](../../docs/push-vs-migrate.md).
