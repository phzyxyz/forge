import { expect, test } from "@playwright/test";

/**
 * Diamond D5 — action catalog drives menus; export + bulk confirm.
 */
test.describe("AdminBoard diamond D5", () => {
  test("export from registry and bulk activate confirm", async ({ page }) => {
    await page.goto("/admin/");
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-username").fill("admin");
    await page.getByTestId("login-password").fill("phzyx");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("nav-users").click();
    await expect(page.getByTestId("resource-page-users")).toBeVisible();

    // Global actions from registry (export)
    await page.getByTestId("overflow-menu").click();
    await expect(page.getByRole("menuitem", { name: "Export CSV" })).toBeVisible();
    await page.keyboard.press("Escape");

    // Bulk deactivate still works via registry
    await page.getByTestId("table-row").first().getByLabel("Select row").check();
    await expect(page.getByTestId("bulk-bar")).toBeVisible();
    await expect(page.getByTestId("bulk-action-deactivate")).toBeVisible();
    await page.getByTestId("bulk-action-deactivate").click();
    await page.getByRole("button", { name: "Confirm" }).click();

    // Row actions menu present (registry: Activate + Deactivate)
    await page.getByTestId("row-actions").first().click();
    await expect(page.getByRole("menuitem", { name: "Deactivate" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Activate", exact: true })).toBeVisible();
  });
});
