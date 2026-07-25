import { expect, test } from "@playwright/test";

/**
 * Diamond D4 — FK typeahead + has-many relation panel.
 */
test.describe("AdminBoard diamond D4", () => {
  test("fk autocomplete and user relation panel", async ({ page }) => {
    await page.goto("/admin/");
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-username").fill("admin");
    await page.getByTestId("login-password").fill("phzyx");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 15_000 });

    // Posts — FK typeahead on author
    await page.getByTestId("nav-posts").click();
    await expect(page.getByTestId("resource-page-posts")).toBeVisible();
    await page.getByTestId("new-record").click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    // int PK autoincrement — not shown on create
    await expect(page.getByTestId("field-id")).toHaveCount(0);
    const title = `D4 Post ${Date.now() % 1_000_000}`;
    await page.getByTestId("field-title").fill(title);
    await page.getByTestId("field-author_id").click();
    await page.getByTestId("field-author_id").fill("ops");
    await expect(page.getByTestId("fk-options-author_id")).toBeVisible({ timeout: 10_000 });
    // first matching FK option (seed user "ops")
    await page.locator('[data-testid^="fk-option-"]').first().click();
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });

    // Users — relation panels for memberships + posts
    await page.getByTestId("nav-users").click();
    await expect(page.getByTestId("resource-page-users")).toBeVisible();
    await page.getByTestId("table-row").first().click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    await expect(page.getByTestId("relation-panels")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("relation-panel-memberships")).toBeVisible();
    await expect(page.getByTestId("relation-panel-posts")).toBeVisible();
  });
});
