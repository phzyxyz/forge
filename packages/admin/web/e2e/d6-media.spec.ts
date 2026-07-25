import { expect, test } from "@playwright/test";
import { loginAsAdmin } from "./helpers";

test.describe("Diamond D6 Media", () => {
  test("login → media dropzone → library thumbs", async ({ page }) => {
    await loginAsAdmin(page);

    await page.getByTestId("nav-media").click();
    await expect(page.getByTestId("media-page")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("media-dropzone")).toBeVisible();
    // Live demo seed always ships library keys
    await expect(page.getByTestId("media-card").first()).toBeVisible({ timeout: 20_000 });
  });
});
