export type ColumnSchema = {
  name: string;
  label: string;
  readonly?: boolean;
  searchable?: boolean;
  sortable?: boolean;
  exportable?: boolean;
  hidden?: boolean;
  file_kind?: string | null;
  filterable?: boolean;
  filter_type?: "text" | "bool" | "number" | "choice" | string;
  filter_ops?: string[];
  widget?: string;
  required?: boolean;
  autoincrement?: boolean;
  read_perm?: string | null;
  write_perm?: string | null;
  fk_resource?: string | null;
  fk_column?: string | null;
  fk_label_fields?: string[];
  m2m_resource?: string | null;
  m2m_relation?: string | null;
};

export type FieldsetSchema = {
  name: string;
  label: string;
  fields: string[];
};

export type RelationSchema = {
  name: string;
  label: string;
  resource: string;
  foreign_key: string;
  kind?: string;
  through?: string | null;
  through_local?: string | null;
  through_remote?: string | null;
};

export type AutocompleteOption = {
  value: string | number;
  label: string;
  identity?: string;
  record?: Record<string, unknown>;
};

export type ResourceSchema = {
  name: string;
  label: string;
  primary_key: string[];
  readonly?: boolean;
  searchable?: string[];
  filterable?: string[];
  filter_ops?: string[];
  default_sort?: string;
  fieldsets?: FieldsetSchema[];
  relations?: RelationSchema[];
  columns: ColumnSchema[];
};

export type SchemaStatus = {
  ok: boolean;
  error?: string | null;
  dialect?: string | null;
  version?: string | null;
  capabilities?: string[];
  migrations?: { applied: string[]; pending: string[]; note?: string };
  plan_summary?: string | null;
  migrations_dir?: string | null;
};

export type ListResult = {
  items: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
  next_cursor: string | null;
  prev_cursor: string | null;
  has_more: boolean;
  pagination?: "offset" | "keyset" | string;
  filters?: Record<string, string>;
};

export type BulkActionInfo = {
  name: string;
  label: string;
  description?: string;
  confirm?: boolean;
  danger?: boolean;
  scope?: "row" | "bulk" | "global" | string;
  client?: string | null;
};

/** Diamond D5 action descriptor (row / bulk / global). */
export type AdminActionInfo = BulkActionInfo;

export type BrandingInfo = {
  site_title: string;
  header_title: string;
  header_subtitle: string;
  show_powered_by: boolean;
};

export type MetaInfo = {
  theme: string;
  themes: string[];
  prefix: string;
  version: string;
  branding?: BrandingInfo;
};

export type ToastKind = "ok" | "error";
export type ToastItem = { id: string; message: string; kind: ToastKind };
export type DrawerMode = "create" | "view" | "edit" | null;
export type ThemePref = "stellar-dark" | "magical-white" | "system-ambient";
export type Density = "comfortable" | "compact";

export type AppRoute =
  | { page: "overview" }
  | { page: "resource"; name: string }
  | { page: "media" }
  | { page: "settings" }
  | { page: "login" }
  | { page: "schema" }
  | { page: "audit" }
  | { page: "apidocs" };

/** localStorage saved table view (Diamond D2). */
export type SavedView = {
  filters: Record<string, string>;
  columnVisibility: Record<string, boolean>;
  columnOrder: string[];
  pageSize: number;
  pagination: "offset" | "keyset";
};
