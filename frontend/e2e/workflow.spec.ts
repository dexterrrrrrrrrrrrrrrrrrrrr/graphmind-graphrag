import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
test("upload → three-hop answer → graph provenance → comparison → benchmark", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", {name: "Connected knowledge. Clear answers."})).toBeVisible();
  await page.getByRole("link", {name: "Documents", exact: true}).click();
  await page
    .locator("input[type=file]")
    .setInputFiles(
      ["01-founder.txt", "02-acquisition.txt", "03-partnership.txt"].map((n) =>
        fileURLToPath(new URL("../../datasets/demo/" + n, import.meta.url)),
      ),
    );
  await expect(page.locator("span.status.ready")).toHaveCount(3, {
    timeout: 60000,
  });
  await page.getByRole("link", { name: "Ask GraphMind" }).click();
  await page
    .getByRole("textbox", { name: "Your question" })
    .fill(
      "Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?",
    );
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".answer-text")).toContainText("MedCore");
  await expect(page.locator(".citation")).toHaveCount(3);
  await page.getByRole("link", { name: /Highlight these paths/ }).click();
  await expect(page.locator(".graph-canvas")).toHaveAttribute(
    "aria-label",
    /4 entities and 3 relationships/,
  );
  await page.getByRole("textbox", { name: "Search entities" }).fill("Rahul");
  await expect(page.locator(".graph-canvas")).toHaveAttribute("aria-label", /1 entities and 0 relationships/);
  await page.getByRole("link", { name: "Comparison lab" }).click();
  await page
    .getByRole("textbox", { name: "Comparison question" })
    .fill(
      "Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?",
    );
  await page.getByRole("button", { name: "Compare strategies" }).click();
  await expect(page.locator(".answer-text")).toHaveCount(2);
  await expect(page.locator(".answer-text").nth(1)).toContainText("MedCore");
  await page.getByRole("button", { name: "Run benchmark" }).click();
  await expect(page.getByRole("link", { name: "CSV" }).first()).toBeVisible({
    timeout: 60000,
  });
  await page.getByRole("link", { name: "Analytics", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Query latency" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Save configuration" }).click();
  await expect(page.getByRole("status").filter({hasText: "Settings saved"})).toBeVisible();
  expect(errors).toEqual([]);
});
