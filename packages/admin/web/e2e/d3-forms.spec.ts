import { expect, test } from "@playwright/test";
import { loginAsAdmin, openCreateDrawer, openResource, searchForText } from "./helpers";

/**
 * Diamond D3 — fieldsets, widgets, dirty guard, field errors.
 */
test.describe("AdminBoard diamond D3", () => {
  test("form widgets fieldsets dirty and 422", async ({ page }) => {
    await loginAsAdmin(page);
    await openResource(page, "users");

    // Open create — fieldsets + widgets
    await openCreateDrawer(page);
    await expect(page.getByTestId("fieldset-identity")).toBeVisible();
    await expect(page.getByTestId("fieldset-details")).toBeVisible();
    await expect(page.getByTestId("field-joined")).toBeVisible();
    await expect(page.getByTestId("field-notes")).toBeVisible();
    await expect(page.getByTestId("field-active")).toBeVisible();

    // Dirty guard
    await page.getByTestId("field-name").fill("Partial");
    await expect(page.getByTestId("dirty-badge")).toBeVisible();
    await page.getByTestId("drawer-close").click();
    await expect(page.getByRole("heading", { name: "Discard unsaved changes?" })).toBeVisible();
    await page
      .getByRole("dialog", { name: "Discard unsaved changes?" })
      .getByRole("button", { name: "Cancel" })
      .click();
    await expect(page.getByTestId("record-drawer")).toBeVisible();

    // 422 field errors (missing email). PK is autoincrement — not on create form.
    const uid = String(Date.now() % 1_000_000_000);
    await page.getByTestId("field-name").fill("D3 User");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("field-error-email")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("form-error")).toBeVisible();

    // Complete + save
    const email = `d3-${uid}@phzyx.xyz`;
    await page.getByTestId("field-email").fill(email);
    await page.getByTestId("field-joined").fill("2025-03-01");
    await page.getByTestId("field-notes").fill("Diamond form");
    await page.getByTestId("drawer-save").click();
    await expect(page.getByTestId("record-drawer")).toBeHidden({ timeout: 15_000 });
    await searchForText(page, email);
  });
});
