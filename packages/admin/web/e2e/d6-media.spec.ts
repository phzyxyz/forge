import { test, expect } from "@playwright/test";

test.describe("Diamond D6 Media", () => {
  test("login → media dropzone → library thumbs", async ({ page }) => {
    await page.goto("/admin/");
    await expect(page.getByTestId("login-page")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-username").fill("admin");
    await page.getByTestId("login-password").fill("phzyx");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-page")).toBeHidden({ timeout: 15_000 });

    await page.getByTestId("nav-media").click();
    await expect(page.getByTestId("media-page")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("media-dropzone")).toBeVisible();
    await expect(page.getByTestId("media-card").first()).toBeVisible({ timeout: 10_000 });
  });
});
