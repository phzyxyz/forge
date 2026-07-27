import { describe, expect, it } from "vitest";
import { resourceNavIcon } from "./Icons";

describe("resourceNavIcon", () => {
  it("maps SaaS / auth / ecommerce / CRM-style table names distinctly", () => {
    for (const name of [
      "users",
      "organizations",
      "memberships",
      "posts",
      "comments",
      "tags",
      "invoices",
      "assets",
      "projects",
      "phzyx_auth_sessions",
      "phzyx_auth_api_keys",
      "phzyx_auth_audit_events",
      "oauth_accounts",
      "mfa_devices",
      // ecommerce
      "products",
      "product_variants",
      "shopping_carts",
      "cart_items",
      "orders",
      "order_items",
      "coupons",
      "shipments",
      "warehouses",
      "vendors",
      "product_reviews",
      // CRM / support
      "leads",
      "opportunities",
      "support_tickets",
      "campaigns",
      // LMS
      "courses",
      "lessons",
      "enrollments",
      // social
      "followers",
      "likes",
      "notifications",
      // fintech
      "wallets",
      "bank_transfers",
      // booking
      "reservations",
      "hotel_rooms",
    ]) {
      expect(typeof resourceNavIcon(name)).toBe("function");
    }
    expect(resourceNavIcon("memberships")).not.toBe(resourceNavIcon("users"));
    expect(resourceNavIcon("cart_items")).toBe(resourceNavIcon("memberships")); // both links
    expect(resourceNavIcon("products")).not.toBe(resourceNavIcon("orders"));
    expect(resourceNavIcon("courses")).not.toBe(resourceNavIcon("invoices"));
    expect(resourceNavIcon("leads")).not.toBe(resourceNavIcon("products"));
    expect(resourceNavIcon("coupons")).not.toBe(resourceNavIcon("orders"));
  });

  it("returns stable fallback for unknown names", () => {
    const a = resourceNavIcon("zzzy_unknown_widget_42");
    const b = resourceNavIcon("zzzy_unknown_widget_42");
    expect(a).toBe(b);
  });
});
