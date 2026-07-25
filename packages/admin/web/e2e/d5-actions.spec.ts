import { expect, test } from "@playwright/test";
import { clickConfirm, loginAsAdmin, openResource } from "./helpers";

/**
 * Diamond D5 — action catalog drives menus; export + bulk confirm.
 */
test.describe("AdminBoard diamond D5", () => {
  test("export from registry and bulk activate confirm", async ({ page }) => {
    await loginAsAdmin(page);
    await openResource(page, "users");

    // Global actions from registry (export)
    await page.getByTestId("overflow-menu").click();
    await expect(page.getByRole("menuitem", { name: "Export CSV" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menuitem", { name: "Export CSV" })).toBeHidden({
      timeout: 5_000,
    });

    // Bulk deactivate via registry
    await page.getByTestId("table-row").first().getByLabel("Select row").check();
    await expect(page.getByTestId("bulk-bar")).toBeVisible();
    await expect(page.getByTestId("bulk-action-deactivate")).toBeVisible();
    await page.getByTestId("bulk-action-deactivate").click();
    await clickConfirm(page);

    // Row actions menu present (registry: Activate + Deactivate)
    await page.getByTestId("row-actions").first().click();
    await expect(page.getByRole("menuitem", { name: "Deactivate" })).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("menuitem", { name: "Activate", exact: true })).toBeVisible();
  });
});
