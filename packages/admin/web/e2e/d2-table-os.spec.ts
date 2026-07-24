import { expect, test } from "@playwright/test";

/**
 * Diamond D2 — filters + bulk deactivate (live demo :9100).
 */
test.describe("AdminBoard diamond D2", () => {
  test("filter active and bulk deactivate", async ({ page }) => {
    await page.goto("/admin/");
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-username").fill("admin");
    await page.getByTestId("login-password").fill("phzyx");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("nav-users").click();
    await expect(page.getByTestId("resource-page-users")).toBeVisible();
    await expect(page.getByTestId("filter-bar")).toBeVisible();

    // Filter to active only
    await page.getByTestId("filter-input-active").selectOption("true");
    await expect(page.getByTestId("filter-chip-active")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("table-row").first()).toBeVisible();

    // Select first row via checkbox (avoid opening drawer)
    await page.getByTestId("table-row").first().getByLabel("Select row").check();
    await expect(page.getByTestId("bulk-bar")).toBeVisible();
    await expect(page.getByTestId("bulk-action-deactivate")).toBeVisible();
    await page.getByTestId("bulk-action-deactivate").click();
    await page.getByRole("button", { name: "Confirm" }).click();

    // Keyset toggle present
    await page.getByTestId("keyset-toggle").check();
    await expect(page.getByTestId("page-indicator")).toContainText(/Keyset/i);
  });
});
