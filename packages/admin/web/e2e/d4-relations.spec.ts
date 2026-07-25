import { expect, test } from "@playwright/test";
import { loginAsAdmin, openCreateDrawer, openResource, searchForText } from "./helpers";

/**
 * Diamond D4 — FK typeahead + has-many relation panel.
 */
test.describe("AdminBoard diamond D4", () => {
  test("fk autocomplete and user relation panel", async ({ page }) => {
    await loginAsAdmin(page);

    // Posts — FK typeahead on author
    await openResource(page, "posts");
    await openCreateDrawer(page);
    const title = `D4 Post ${Date.now() % 1_000_000}`;
    await page.getByTestId("field-title").fill(title);
    await page.getByTestId("field-author_id").click();
    await page.getByTestId("field-author_id").fill("ops");
    await expect(page.getByTestId("fk-options-author_id")).toBeVisible({ timeout: 15_000 });
    await page.locator('[data-testid^="fk-option-"]').first().click();
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });
    // Multi-page posts seed — search for created title
    await searchForText(page, title);

    // Users — relation panels for memberships + posts
    await openResource(page, "users");
    await page.getByTestId("table-row").first().click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();
    await expect(page.getByTestId("relation-panels")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("relation-panel-memberships")).toBeVisible();
    await expect(page.getByTestId("relation-panel-posts")).toBeVisible();
  });
});
