import { describe, expect, it } from "vitest";
import { inferWidgetName, resolveWidget } from "./registry";
import type { ColumnSchema } from "../../../shared/api/types";

describe("widget registry diamond D3", () => {
  it("resolves known widgets", () => {
    const boolCol: ColumnSchema = {
      name: "active",
      label: "Active",
      widget: "bool",
    };
    expect(inferWidgetName(boolCol)).toBe("bool");
    expect(resolveWidget(boolCol)).toBeTypeOf("function");
    expect(resolveWidget({ name: "joined", label: "Joined", widget: "date" })).toBeTypeOf(
      "function",
    );
    expect(resolveWidget({ name: "meta", label: "Meta", widget: "json" })).toBeTypeOf("function");
  });

  it("falls back to text for unknown", () => {
    const w = resolveWidget({ name: "x", label: "X", widget: "nope-widget" });
    expect(w).toBeTypeOf("function");
  });
});
