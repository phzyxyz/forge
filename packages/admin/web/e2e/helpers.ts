import { expect, type Page } from "@playwright/test";

/** Sign in and land on overview (demo default admin/phzyx). */
export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto("/admin/");
  await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("login-username").fill("admin");
  await page.getByTestId("login-password").fill("phzyx");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-page")).toBeHidden({ timeout: 20_000 });
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 15_000 });
}

/** Open a resource nav item and wait for its table. */
export async function openResource(page: Page, name: string): Promise<void> {
  await page.getByTestId(`nav-${name}`).click();
  await expect(page.getByTestId(`resource-page-${name}`)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("resource-table")).toBeVisible({ timeout: 15_000 });
  // Prefer at least one row when the resource is seeded
  await expect(page.getByTestId("table-row").first()).toBeVisible({ timeout: 15_000 });
}

/**
 * Search list so a newly created row is on-screen (full seed is multi-page).
 * SPA debounces search ~250ms — assert via filtered table row.
 */
export async function searchForText(page: Page, text: string): Promise<void> {
  const search = page.getByTestId("resource-search");
  await search.fill("");
  await search.fill(text);
  await expect(
    page.getByTestId("table-row").filter({ hasText: text }).first(),
  ).toBeVisible({ timeout: 20_000 });
}

/** Open create drawer; assert autoincrement int PK is not shown. */
export async function openCreateDrawer(page: Page): Promise<void> {
  await page.getByTestId("new-record").click();
  await expect(page.getByTestId("record-drawer")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("field-id")).toHaveCount(0);
}

/** Confirm bulk/dialog Confirm button when present. */
export async function clickConfirm(page: Page): Promise<void> {
  const btn = page.getByRole("button", { name: "Confirm" });
  await expect(btn).toBeVisible({ timeout: 10_000 });
  await btn.click();
}
