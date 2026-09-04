import { expect, test } from "@playwright/test";
import { mockPulseApi, seedSession } from "./mock-api";

test.describe("Product history windows", () => {
  test("loads the last 7 days and pages older on demand", async ({ page }) => {
    await seedSession(page);
    await mockPulseApi(page);
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/products/B09RKS585V");

    const price = page.getByTestId("price-history");
    await expect(price.getByRole("heading", { name: "Price history" })).toBeVisible();
    await expect(price.getByRole("cell", { name: "2026-09-04" })).toBeVisible();
    await expect(price.getByRole("cell", { name: "£8.45" })).toBeVisible();
    await expect(price.getByRole("button", { name: "Newer" })).toBeDisabled();

    await price.getByRole("button", { name: "Older" }).click();
    await expect(price.getByRole("cell", { name: "2026-08-22" })).toBeVisible();
    await expect(price.getByRole("cell", { name: "£7.99" })).toBeVisible();
    await expect(price.getByRole("button", { name: "Newer" })).toBeEnabled();

    const reviews = page.getByTestId("review-history");
    await expect(reviews.getByRole("heading", { name: "Review momentum" })).toBeVisible();
    await expect(reviews.getByRole("cell", { name: "6,080" })).toBeVisible();
  });

  test("history pagers stay usable on a phone viewport", async ({ page }) => {
    await seedSession(page);
    await mockPulseApi(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/products/B09RKS585V");

    const pager = page.getByTestId("history-pager").first();
    await expect(pager).toBeVisible();
    const box = await pager.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeLessThanOrEqual(390);
    await expect(pager.getByRole("button", { name: "Older" })).toBeVisible();
    await expect(pager.getByRole("button", { name: "Newer" })).toBeVisible();
  });
});
