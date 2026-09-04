import { expect, test } from "@playwright/test";
import { mockPulseApi } from "./mock-api";

test("login reaches the Watchlist", async ({ page }) => {
  await mockPulseApi(page);
  await page.goto("/login");
  await page.getByLabel("Username").fill("basil");
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Amazon Pulse" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ilex Wood Deodorant" }).first()).toBeVisible();
});
