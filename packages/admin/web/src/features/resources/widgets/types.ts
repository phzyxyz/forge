import type { ColumnSchema } from "../../../shared/api/types";

export type WidgetName =
  | "text"
  | "number"
  | "bool"
  | "date"
  | "datetime"
  | "textarea"
  | "json"
  | "file"
  | "fk"
  | "m2m"
  | string;

export type FieldWidgetProps = {
  column: ColumnSchema;
  value: string;
  readOnly: boolean;
  error?: string;
  onChange: (value: string) => void;
};

export type FieldWidget = (props: FieldWidgetProps) => React.ReactNode;
