import { describe, expect, it } from "vitest";
import { coerceBody, rowToDraft } from "./format";

describe("coerceBody", () => {
  it("coerces numbers and booleans", () => {
    expect(coerceBody({ id: "7", active: "true", name: "Ada" })).toEqual({
      id: 7,
      active: true,
      name: "Ada",
    });
  });

  it("skips empty strings", () => {
    expect(coerceBody({ email: "" })).toEqual({});
  });
});

describe("rowToDraft", () => {
  it("stringifies and drops identity", () => {
    expect(rowToDraft({ id: 1, active: true, _identity: "1" })).toEqual({
      id: "1",
      active: "true",
    });
  });
});
