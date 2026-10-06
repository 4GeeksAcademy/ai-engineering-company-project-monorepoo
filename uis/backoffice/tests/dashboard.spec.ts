import { expect, test } from "@playwright/test";

test("loads secondary panels only when selected, without layout overflow", async ({ page }, testInfo) => {
  const scripts = new Set<string>();
  const errors: string[] = [];
  page.on("request", (request) => {
    if (request.resourceType() === "script") scripts.add(request.url());
  });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Stock", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Proveedores", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "RRHH", exact: true })).toHaveCount(0);
  const initialScripts = new Set(scripts);

  await page.getByRole("button", { name: "Proveedores", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Proveedores", exact: true })).toBeVisible();
  await expect(page.getByText(/Carnes Andinas subio/)).toBeVisible();
  const supplierScripts = [...scripts].filter((url) => !initialScripts.has(url));
  expect(supplierScripts.length).toBeGreaterThan(0);
  const afterSupplier = new Set(scripts);

  await page.getByRole("button", { name: "RRHH", exact: true }).click();
  await expect(page.getByRole("heading", { name: "RRHH", exact: true })).toBeVisible();
  await expect(page.getByText("Rotacion alta en US: 21%.")).toBeVisible();
  const hrScripts = [...scripts].filter((url) => !afterSupplier.has(url));
  expect(hrScripts.length).toBeGreaterThan(0);
  const afterHr = new Set(scripts);

  await page.getByRole("button", { name: "Proveedores", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Proveedores", exact: true })).toBeVisible();
  expect([...scripts]).toEqual([...afterHr]);
  await expect(page.getByRole("button", { name: "Proveedores", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const overflow = await page.locator("h1, h2, h3, button, .metric").evaluateAll((elements) =>
    elements.some((element) => {
      const bounds = element.getBoundingClientRect();
      return bounds.left < 0 || bounds.right > window.innerWidth || element.scrollWidth > element.clientWidth;
    })
  );
  expect(overflow).toBe(false);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("dashboard.png"), fullPage: true });
  await testInfo.attach("lazy-chunks", {
    body: JSON.stringify({ initial: initialScripts.size, supplierScripts, hrScripts }, null, 2),
    contentType: "application/json",
  });
});