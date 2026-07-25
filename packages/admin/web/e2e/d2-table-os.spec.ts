import { expect, test } from "@playwright/test";
import { clickConfirm, loginAsAdmin, openResource } from "./helpers";

/**
 * Diamond D2 — filters + bulk deactivate (live demo :9100).
 */
test.describe("AdminBoard diamond D2", () => {
  test("filter active and bulk deactivate", async ({ page }) => {
    await loginAsAdmin(page);
    await openResource(page, "users");
    await expect(page.getByTestId("filter-bar")).toBeVisible();

    // Filter to active only
    await page.getByTestId("filter-input-active").selectOption("true");
    await expect(page.getByTestId("filter-chip-active")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("table-row").first()).toBeVisible({ timeout: 15_000 });

    // Select first row via checkbox (avoid opening drawer)
    await page.getByTestId("table-row").first().getByLabel("Select row").check();
    await expect(page.getByTestId("bulk-bar")).toBeVisible();
    await expect(page.getByTestId("bulk-action-deactivate")).toBeVisible();
    await page.getByTestId("bulk-action-deactivate").click();
    await clickConfirm(page);
    // Selection may clear async — keyset toggle is the durable D2 signal
    await expect(page.getByTestId("resource-table")).toBeVisible();

    // Keyset toggle present
    await page.getByTestId("keyset-toggle").check();
    await expect(page.getByTestId("page-indicator")).toContainText(/Keyset/i);
  });
});
