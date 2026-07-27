import { describe, expect, it } from "vitest";
import { filterWireKey, parseFilterWireKey } from "./FilterBar";

describe("filter wire keys", () => {
  it("encodes eq as bare field", () => {
    expect(filterWireKey("email", "eq")).toBe("email");
  });

  it("encodes other ops with __", () => {
    expect(filterWireKey("email", "contains")).toBe("email__contains");
    expect(filterWireKey("score", "gte")).toBe("score__gte");
  });

  it("parses bare and op keys", () => {
    expect(parseFilterWireKey("email")).toEqual({ field: "email", op: "eq" });
    expect(parseFilterWireKey("email__contains")).toEqual({
      field: "email",
      op: "contains",
    });
    expect(parseFilterWireKey("a__b__c")).toEqual({ field: "a__b", op: "c" });
  });
});
