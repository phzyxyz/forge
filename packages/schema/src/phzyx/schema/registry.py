"""Model registry — discover concrete Phzyx models by class or table name."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phzyx.schema.model import Model


class RegistryError(Exception):
    """Invalid registry operation (duplicate table, missing model, …)."""


class ModelRegistry:
    """In-process registry of concrete :class:`~phzyx.schema.model.Model` subclasses.

    Models are keyed by:

    * fully-qualified class name (``module.QualName``)
    * qualified table name (``schema.table`` or ``table``)

    Concrete models auto-register on class creation unless
    ``class Meta: register = False``.
    """

    def __init__(self) -> None:
        self._by_qualname: dict[str, type[Model]] = {}
        self._by_table: dict[str, type[Model]] = {}

    def register(self, model: type[Model], *, replace: bool = False) -> type[Model]:
        """Register a concrete model.

        Parameters
        ----------
        model:
            Model subclass with a populated ``__phzyx_table__``.
        replace:
            If true, overwrite an existing entry for the same table/qualname.

        Raises
        ------
        RegistryError
            Abstract models, missing table info, or conflicting table names.
        """
        from phzyx.schema.model import Model, get_table_info

        if not isinstance(model, type) or not issubclass(model, Model):
            raise RegistryError(f"expected a Model subclass, got {model!r}")

        try:
            info = get_table_info(model)
        except TypeError as exc:
            raise RegistryError(str(exc)) from exc

        qualname = info.model_qualname
        table_key = info.qualified_name

        if not replace:
            existing_q = self._by_qualname.get(qualname)
            if existing_q is not None and existing_q is not model:
                raise RegistryError(f"model already registered: {qualname}")
            existing_t = self._by_table.get(table_key)
            if existing_t is not None and existing_t is not model:
                raise RegistryError(
                    f"table {table_key!r} already registered by "
                    f"{existing_t.__module__}.{existing_t.__qualname__}; "
                    f"cannot also register {qualname}"
                )

        # Drop previous keys if re-registering the same class under new table.
        self._drop_model(model)

        self._by_qualname[qualname] = model
        self._by_table[table_key] = model
        return model

    def unregister(self, model: type[Model]) -> None:
        """Remove a model if present (no error if missing)."""
        self._drop_model(model)

    def get(self, qualname: str) -> type[Model]:
        """Lookup by fully-qualified class name (``module.Class``)."""
        try:
            return self._by_qualname[qualname]
        except KeyError as exc:
            raise RegistryError(f"no model registered for qualname {qualname!r}") from exc

    def get_by_table(self, table: str, *, schema: str | None = None) -> type[Model]:
        """Lookup by table name, optionally with schema."""
        key = f"{schema}.{table}" if schema else table
        try:
            return self._by_table[key]
        except KeyError as exc:
            raise RegistryError(f"no model registered for table {key!r}") from exc

    def contains(self, model: type[Model]) -> bool:
        """Return whether the model class is registered."""
        from phzyx.schema.model import get_table_info

        try:
            info = get_table_info(model)
        except TypeError:
            return False
        return self._by_qualname.get(info.model_qualname) is model

    def models(self) -> tuple[type[Model], ...]:
        """All registered models in insertion order."""
        return tuple(self._by_qualname.values())

    def tables(self) -> tuple[str, ...]:
        """Qualified table names currently registered."""
        return tuple(self._by_table.keys())

    def clear(self) -> None:
        """Remove all registrations (useful in tests)."""
        self._by_qualname.clear()
        self._by_table.clear()

    def __len__(self) -> int:
        return len(self._by_qualname)

    def __iter__(self) -> Iterable[type[Model]]:
        return iter(self._by_qualname.values())

    def _drop_model(self, model: type[Model]) -> None:
        qual_keys = [k for k, v in self._by_qualname.items() if v is model]
        for k in qual_keys:
            del self._by_qualname[k]
        table_keys = [k for k, v in self._by_table.items() if v is model]
        for k in table_keys:
            del self._by_table[k]


_default_registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    """Return the process-wide default model registry."""
    return _default_registry


def register_model(model: type[Model], *, replace: bool = False) -> type[Model]:
    """Register ``model`` on the default registry."""
    return _default_registry.register(model, replace=replace)


def unregister_model(model: type[Model]) -> None:
    """Unregister ``model`` from the default registry."""
    _default_registry.unregister(model)
