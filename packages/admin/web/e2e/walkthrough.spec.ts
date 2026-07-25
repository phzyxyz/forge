import { expect, test } from "@playwright/test";

/**
 * Diamond D1 critical path — release blocker.
 * Requires live demo: http://127.0.0.1:9100
 */
test.describe("AdminBoard diamond D1", () => {
  test("full reliability walkthrough", async ({ page }) => {
    await page.goto("/admin/");

    // Sign in page only (no browser Basic dialog dependency)
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-username").fill("admin");
    await page.getByTestId("login-password").fill("phzyx");
    await page.getByTestId("login-submit").click();

    await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("app-shell")).toBeVisible();

    // Users resource
    await page.getByTestId("nav-users").click();
    await expect(page.getByTestId("resource-page-users")).toBeVisible();
    await expect(page.getByTestId("resource-table")).toBeVisible();

    // Row click opens drawer (never blank)
    await page.getByTestId("table-row").first().click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    await expect(page.getByTestId("drawer-title")).toBeVisible();

    // Edit + save
    await page.getByTestId("drawer-edit").click();
    await page.getByTestId("field-name").fill("Ops Updated");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 10_000 });

    // Create user — int PK is autoincrement (hidden on create)
    const uid = String(Date.now() % 1_000_000_000);
    const email = `d1-${uid}@phzyx.xyz`;
    await page.getByTestId("new-record").click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    await expect(page.getByTestId("field-id")).toHaveCount(0);
    await page.getByTestId("field-email").fill(email);
    await page.getByTestId("field-name").fill("Diamond");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });
    await expect(page.getByText(email)).toBeVisible({ timeout: 10_000 });

    // Overflow export menu
    await page.getByTestId("overflow-menu").click();
    await expect(page.getByRole("menuitem", { name: "Export CSV" })).toBeVisible();
    await page.keyboard.press("Escape");

    // Media preview (first card may be image, text, or other — not always img)
    await page.getByTestId("nav-media").click();
    await expect(page.getByTestId("media-page")).toBeVisible();
    const card = page.getByTestId("media-card").first();
    await expect(card).toBeVisible();
    await card.click();
    await expect(page.getByTestId("file-preview")).toBeVisible();
    await expect(
      page
        .getByTestId("file-preview-img")
        .or(page.getByTestId("file-preview-text"))
        .or(page.getByTestId("file-preview-pdf")),
    ).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("file-preview-close").click();

    // Sign out → login
    await page.getByTestId("sign-out").click();
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 10_000 });

    // After sign-out, API must 401 without credentials (SPA session cleared)
    const meta = await page.request.get("/admin/api/v1/meta");
    expect(meta.status()).toBe(401);
    expect(meta.headers()["www-authenticate"]).toBeUndefined();
  });
});
