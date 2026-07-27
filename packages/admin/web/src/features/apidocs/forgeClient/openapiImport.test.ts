import { describe, expect, it } from "vitest";
import { defaultSettings } from "./defaults";
import {
  exampleFromSchema,
  openApiToCollection,
  sampleBodyFromOperation,
  shouldHidePath,
} from "./openapiImport";
import type { OpenApiSpec } from "../openapiTypes";

describe("openapiImport", () => {
  it("hides /admin paths by default", () => {
    const s = defaultSettings();
    expect(shouldHidePath("/admin/api/v1/resources", s)).toBe(true);
    expect(shouldHidePath("/orders", s)).toBe(false);
    expect(shouldHidePath("/administration", s)).toBe(false);
  });

  it("builds sample body from schema", () => {
    const body = sampleBodyFromOperation({
      requestBody: {
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                name: { type: "string" },
                qty: { type: "integer" },
              },
            },
          },
        },
      },
    });
    expect(JSON.parse(body)).toEqual({ name: "string", qty: 0 });
  });

  it("exampleFromSchema handles arrays and enums", () => {
    expect(
      exampleFromSchema({
        type: "array",
        items: { type: "string", enum: ["a", "b"] },
      }),
    ).toEqual(["a"]);
  });

  it("openApiToCollection filters admin and groups by tag", () => {
    const spec: OpenApiSpec = {
      paths: {
        "/admin/api/v1/x": {
          get: { tags: ["admin"], summary: "Internal" },
        },
        "/orders": {
          get: { tags: ["orders"], summary: "List orders" },
          post: {
            tags: ["orders"],
            summary: "Create",
            requestBody: {
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: { sku: { type: "string" } },
                  },
                },
              },
            },
          },
        },
      },
    };
    const col = openApiToCollection(spec, defaultSettings());
    const paths = col.folders.flatMap((f) => f.requests.map((r) => r.path));
    expect(paths).toEqual(["/orders", "/orders"]);
    expect(col.folders[0]?.name).toBe("orders");
    const create = col.folders[0]?.requests.find((r) => r.method === "POST");
    expect(create?.body.raw).toContain("sku");
  });
});
