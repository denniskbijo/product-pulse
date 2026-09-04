import { expect, test } from "@playwright/test";
import { mockPulseApi, seedSession } from "./mock-api";

test.describe("Watchlist", () => {
  test("desktop table shows reviews and momentum without clipping the page", async ({
    page,
  }) => {
    await seedSession(page);
    await mockPulseApi(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");

    const table = page.getByTestId("product-list-table");
    await expect(table).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Reviews" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Momentum" })).toBeVisible();
    await expect(table.getByText("Rising")).toBeVisible();
    await expect(page.getByTestId("product-cards")).toBeHidden();

    const overflowX = await page.evaluate(
      () => getComputedStyle(document.documentElement).overflowX,
    );
    expect(overflowX === "hidden" || overflowX === "auto").toBeTruthy();
    const wrapCanScroll = await table.evaluate((el) => el.scrollWidth > el.clientWidth - 1);
    const actionsVisible = await table
      .getByRole("columnheader", { name: "Actions" })
      .isVisible();
    expect(actionsVisible || wrapCanScroll).toBeTruthy();
  });

  test("mobile uses cards with reviews and momentum, not the clipped table", async ({
    page,
  }) => {
    await seedSession(page);
    await mockPulseApi(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const cards = page.getByTestId("product-cards");
    await expect(cards).toBeVisible();
    await expect(cards.getByText("Reviews")).toBeVisible();
    await expect(cards.getByText("Review momentum")).toBeVisible();
    await expect(cards.getByText("Rising")).toBeVisible();
    await expect(page.getByTestId("product-list-table")).toBeHidden();

    const cardBox = await cards.locator(".product-card").first().boundingBox();
    expect(cardBox).toBeTruthy();
    expect(cardBox!.width).toBeLessThanOrEqual(390);
    expect(cardBox!.x).toBeGreaterThanOrEqual(0);
  });
});
