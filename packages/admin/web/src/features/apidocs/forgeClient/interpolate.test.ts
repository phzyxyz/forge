import { describe, expect, it } from "vitest";
import {
  envMap,
  formatEnvVarDisplay,
  interpolate,
  listUnresolved,
  lookupEnvVar,
  parseEnvTokens,
  resolveRequestUrl,
} from "./interpolate";
import type { Environment } from "./types";

const env: Environment = {
  id: "e1",
  name: "Local",
  variables: [
    { key: "baseUrl", value: "http://127.0.0.1:9100", enabled: true },
    { key: "token", value: "abc", enabled: true, secret: true },
    { key: "off", value: "x", enabled: false },
    { key: "blank", value: "", enabled: true },
  ],
};

describe("interpolate", () => {
  it("replaces enabled variables", () => {
    expect(interpolate("Bearer {{token}}", envMap(env))).toBe("Bearer abc");
  });

  it("leaves unknown tokens", () => {
    expect(interpolate("{{missing}}", envMap(env))).toBe("{{missing}}");
  });

  it("ignores disabled variables", () => {
    expect(interpolate("{{off}}", envMap(env))).toBe("{{off}}");
  });

  it("resolves path-only URLs with baseUrl", () => {
    expect(resolveRequestUrl("/orders", env)).toBe("http://127.0.0.1:9100/orders");
  });

  it("resolves {{baseUrl}} templates", () => {
    expect(resolveRequestUrl("{{baseUrl}}/v1/items", env)).toBe(
      "http://127.0.0.1:9100/v1/items",
    );
  });

  it("lists unresolved", () => {
    expect(listUnresolved("{{a}}/{{token}}", envMap(env))).toEqual(["a"]);
  });
});

describe("parseEnvTokens", () => {
  it("splits text and variables", () => {
    expect(parseEnvTokens("{{baseUrl}}/v1/{{id}}")).toEqual([
      { type: "var", name: "baseUrl", raw: "{{baseUrl}}" },
      { type: "text", value: "/v1/" },
      { type: "var", name: "id", raw: "{{id}}" },
    ]);
  });

  it("returns plain text only", () => {
    expect(parseEnvTokens("/orders")).toEqual([{ type: "text", value: "/orders" }]);
  });
});

describe("lookupEnvVar", () => {
  it("resolves ok / secret / missing / disabled / empty", () => {
    expect(lookupEnvVar(env, "baseUrl")).toEqual({
      status: "ok",
      value: "http://127.0.0.1:9100",
      secret: false,
    });
    expect(lookupEnvVar(env, "token").status).toBe("ok");
    expect(formatEnvVarDisplay(lookupEnvVar(env, "token"))).toBe("••••••••");
    expect(lookupEnvVar(env, "off").status).toBe("disabled");
    expect(lookupEnvVar(env, "blank").status).toBe("empty");
    expect(lookupEnvVar(env, "nope").status).toBe("missing");
  });
});
