// Local capture variant: hits a running pnpm dev server, captures only the
// pages that don't require a live backend. Used to seed the README with
// screenshots before ingestion has been run.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "docs", "screenshots");
const BASE = process.env.WEB_BASE_URL ?? "http://localhost:3000";

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(500);
}

async function shoot(browser, name, route, viewport, fullPage = false) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  await page.goto(`${BASE}${route}`);
  await settle(page);
  await page.screenshot({ path: join(OUT_DIR, `${name}.png`), fullPage });
  await ctx.close();
  console.log(`  ✓ ${name}`);
}

async function shootAskWithError(browser) {
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 1100 },
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/`);
  await settle(page);
  await page.fill(
    'textarea[aria-label="Question"]',
    "What is the minimum corpus size required for a Category I AIF?",
  );
  await page.click('button[aria-label="Ask"]');
  await page.waitForSelector('[role="alert"]', { timeout: 30_000 });
  await page.waitForTimeout(400);
  await page.screenshot({
    path: join(OUT_DIR, "ask-error.png"),
    fullPage: false,
  });
  await ctx.close();
  console.log("  ✓ ask-error");
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  console.log(`base: ${BASE}, out: ${OUT_DIR}`);
  try {
    await shoot(browser, "ask-empty", "/", { width: 1280, height: 900 });
    await shoot(browser, "search", "/search", { width: 1280, height: 900 });
    await shoot(browser, "about", "/about", { width: 1280, height: 1500 }, true);
    await shootAskWithError(browser);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
