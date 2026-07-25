import { expect, test } from "@playwright/test";
import {
  loginAsAdmin,
  openCreateDrawer,
  openResource,
  searchForText,
} from "./helpers";

/**
 * Diamond D1 critical path — release blocker.
 * Requires live demo: http://127.0.0.1:9100
 */
test.describe("AdminBoard diamond D1", () => {
  test("full reliability walkthrough", async ({ page }) => {
    await loginAsAdmin(page);

    await openResource(page, "users");

    // Row click opens drawer (never blank)
    await page.getByTestId("table-row").first().click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    await expect(page.getByTestId("drawer-title")).toBeVisible();

    // Edit + save
    await page.getByTestId("drawer-edit").click();
    await page.getByTestId("field-name").fill("Ops Updated");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });

    // Create user — int PK autoincrement (hidden on create)
    const uid = String(Date.now() % 1_000_000_000);
    const email = `d1-${uid}@phzyx.xyz`;
    await openCreateDrawer(page);
    await page.getByTestId("field-email").fill(email);
    await page.getByTestId("field-name").fill("Diamond");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });
    await searchForText(page, email);

    // Overflow export menu
    await page.getByTestId("overflow-menu").click();
    await expect(page.getByRole("menuitem", { name: "Export CSV" })).toBeVisible();
    await page.keyboard.press("Escape");

    // Media preview (image, text, or pdf)
    await page.getByTestId("nav-media").click();
    await expect(page.getByTestId("media-page")).toBeVisible({ timeout: 15_000 });
    const card = page.getByTestId("media-card").first();
    await expect(card).toBeVisible({ timeout: 15_000 });
    await card.click();
    await expect(page.getByTestId("file-preview")).toBeVisible();
    await expect(
      page
        .getByTestId("file-preview-img")
        .or(page.getByTestId("file-preview-text"))
        .or(page.getByTestId("file-preview-pdf")),
    ).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("file-preview-close").click();

    // Sign out → login
    await page.getByTestId("sign-out").click();
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });

    // After sign-out, API must 401 without credentials (SPA session cleared)
    const meta = await page.request.get("/admin/api/v1/meta");
    expect(meta.status()).toBe(401);
    expect(meta.headers()["www-authenticate"]).toBeUndefined();
  });
});
