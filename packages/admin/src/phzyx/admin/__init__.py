"""Phzyx AdminBoard core — headless admin service and SPA assets."""

from pkgutil import extend_path

from phzyx.admin.actions import (
    AdminAction,
    BulkAction,
    list_admin_actions,
    list_bulk_actions,
    run_admin_action,
    run_bulk_action,
)
from phzyx.admin.async_service import AsyncAdminService
from phzyx.admin.audit import AuditEvent, AuditLog
from phzyx.admin.auth import AllowAll, Authz, DenyWrites, require_authz
from phzyx.admin.errors import (
    AdminError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAdminError,
)
from phzyx.admin.export_copy import copy_payload, export_csv, export_json
from phzyx.admin.i18n import DEFAULT_CATALOG, I18n
from phzyx.admin.identity import decode_identity, encode_identity
from phzyx.admin.layouts import LayoutPrefs, LayoutStore
from phzyx.admin.media import MediaItem, MediaLibrary
from phzyx.admin.opener import OpenMeta, open_meta_for_key
from phzyx.admin.relation_manager import RelationManager, all_relation_managers
from phzyx.admin.resource import (
    ColumnConfig,
    FieldsetConfig,
    RelationConfig,
    ResourceConfig,
    infer_resource,
    m2m_relation,
    override_resource,
    wire_relations,
)
from phzyx.admin.search import SearchHit, global_search
from phzyx.admin.security import (
    assert_no_mass_assignment,
    csp_headers,
    csrf_cookie_notes,
    is_production_like,
)
from phzyx.admin.service import AdminService, ListResult
from phzyx.admin.settings import AdminSettings, SettingsStore
from phzyx.admin.storage import LocalStorage, MemoryStorage, StorageBackend, guess_content_type
from phzyx.admin.storage_cloud import AzureBlobStorage, GCSStorage, S3CompatibleStorage
from phzyx.admin.stream_export import (
    BOUNDED_RSS_NOTE,
    DEFAULT_EXPORT_POLICY,
    EXCEL_MAX_ROWS,
    ExportPolicy,
    export_xlsx,
    stream_csv,
    stream_json_array,
    stream_jsonl,
)
from phzyx.admin.themes import (
    DEFAULT_THEME,
    PRIMARY_THEMES,
    ThemeName,
    normalize_theme,
    resolve_theme,
    theme_tokens_css,
)
from phzyx.admin.widgets import CountWidget, resource_count_widgets

__path__ = extend_path(__path__, __name__)

__version__ = "0.1.7"

__all__ = [
    "BOUNDED_RSS_NOTE",
    "DEFAULT_EXPORT_POLICY",
    "DEFAULT_THEME",
    "EXCEL_MAX_ROWS",
    "PRIMARY_THEMES",
    "AdminAction",
    "AdminError",
    "AdminService",
    "AdminSettings",
    "AsyncAdminService",
    "AllowAll",
    "CountWidget",
    "DEFAULT_CATALOG",
    "I18n",
    "RelationManager",
    "SearchHit",
    "AuditEvent",
    "AuditLog",
    "Authz",
    "AzureBlobStorage",
    "BulkAction",
    "ColumnConfig",
    "ConflictError",
    "DenyWrites",
    "FieldsetConfig",
    "ExportPolicy",
    "ForbiddenError",
    "GCSStorage",
    "LayoutPrefs",
    "LayoutStore",
    "ListResult",
    "LocalStorage",
    "MediaItem",
    "MediaLibrary",
    "MemoryStorage",
    "NotFoundError",
    "OpenMeta",
    "RelationConfig",
    "m2m_relation",
    "ResourceConfig",
    "S3CompatibleStorage",
    "SettingsStore",
    "StorageBackend",
    "ThemeName",
    "UnauthorizedError",
    "ValidationAdminError",
    "__version__",
    "assert_no_mass_assignment",
    "copy_payload",
    "csp_headers",
    "csrf_cookie_notes",
    "decode_identity",
    "encode_identity",
    "all_relation_managers",
    "export_csv",
    "export_json",
    "export_xlsx",
    "global_search",
    "guess_content_type",
    "resource_count_widgets",
    "infer_resource",
    "is_production_like",
    "list_admin_actions",
    "list_bulk_actions",
    "normalize_theme",
    "open_meta_for_key",
    "override_resource",
    "require_authz",
    "resolve_theme",
    "run_admin_action",
    "run_bulk_action",
    "stream_csv",
    "stream_json_array",
    "stream_jsonl",
    "theme_tokens_css",
    "wire_relations",
]
