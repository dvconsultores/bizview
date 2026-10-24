import { expect, type Page } from "@playwright/test";

/**
 * Feature 030 (FR-005): on a phone the report actions collapse into the "⋯" menu, so a spec that
 * runs at 320/375 px opens it first. From 640 px the button is on the row and this is a plain click.
 */
export async function reportAction(page: Page, label: string) {
  const direct = page.getByRole("button", { name: label, exact: true });
  // Spanish or English: some specs switch the interface language first.
  const more = page.getByRole("button", { name: /^(Más acciones|More actions)$/ });
  // The actions row mounts with the report: wait until either shape is on screen.
  await expect(direct.or(more).first()).toBeVisible();
  if (await direct.count()) {
    await direct.first().click();
    return;
  }
  await more.click();
  await page.getByRole("menuitem", { name: label, exact: true }).click();
  await expect(page.getByRole("menu")).toHaveCount(0);
}

/** The same, for an assertion instead of a click: is the action reachable at this width? */
export async function hasReportAction(page: Page, label: string): Promise<boolean> {
  const direct = page.getByRole("button", { name: label, exact: true });
  // Spanish or English: some specs switch the interface language first.
  const more = page.getByRole("button", { name: /^(Más acciones|More actions)$/ });
  await expect(direct.or(more).first()).toBeVisible();
  if (await direct.count()) return true;
  await more.click();
  const item = page.getByRole("menuitem", { name: label, exact: true });
  const found = (await item.count()) > 0;
  await page.keyboard.press("Escape");
  return found;
}
