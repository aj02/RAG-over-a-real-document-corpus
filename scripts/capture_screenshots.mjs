#!/usr/bin/env node
/**
 * Capture the four README screenshots from the running web UI.
 *
 * Usage:
 *   docker compose up -d --build      # API on :8000, web on :3000
 *   python scripts/download_corpus.py
 *   python -m scripts.ingest_cli
 *   node scripts/capture_screenshots.mjs
 *
 * Outputs: docs/screenshots/{ask-empty,ask-answer,search,about}.png
 *
 * Requires playwright. Install once with:
 *   pnpm dlx -p playwright@1 -p @playwright/test playwright install --with-deps chromium
 */

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "docs", "screenshots");
const BASE = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const THEME = process.env.SCREENSHOT_THEME === "dark" ? "dark" : "light";

const SAMPLE_QUESTION =
  "What is the minimum corpus size required for a Category I AIF?";
const SAMPLE_QUERY =
  "KYC requirements for low-risk customers under RBI Master Direction";

async function settle(page) {
  await page.waitForLoadState("networkidle");
  // small extra delay so animations / fonts settle.
  await page.waitForTimeout(300);
}

async function setTheme(page) {
  // next-themes stores preference in localStorage as "theme".
  await page.addInitScript((theme) => {
    try {
      localStorage.setItem("theme", theme);
    } catch {}
  }, THEME);
}

async function captureAskEmpty(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await setTheme(page);
  await page.goto(`${BASE}/`);
  await settle(page);
  const suffix = THEME === "dark" ? "-dark" : "";
  await page.screenshot({
    path: join(OUT_DIR, `ask-empty${suffix}.png`),
    fullPage: false,
  });
  await ctx.close();
}

async function captureAskAnswer(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1400 } });
  const page = await ctx.newPage();
  await setTheme(page);
  await page.goto(`${BASE}/`);
  await settle(page);
  await page.fill('textarea[aria-label="Question"]', SAMPLE_QUESTION);
  await page.click('button[aria-label="Ask"]');
  // wait for either the answer card or an error alert to render
  await page.waitForSelector(
    'section[aria-label="Citations"], [role="alert"]',
    { timeout: 90_000 },
  );
  await settle(page);
  const suffix = THEME === "dark" ? "-dark" : "";
  await page.screenshot({
    path: join(OUT_DIR, `ask-answer${suffix}.png`),
    fullPage: true,
  });
  await ctx.close();
}

async function captureSearch(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1100 } });
  const page = await ctx.newPage();
  await setTheme(page);
  await page.goto(`${BASE}/search`);
  await settle(page);
  await page.fill('textarea[aria-label="Question"]', SAMPLE_QUERY);
  await page.click('button[aria-label="Ask"]');
  await page.waitForSelector("article", { timeout: 60_000 });
  await settle(page);
  const suffix = THEME === "dark" ? "-dark" : "";
  await page.screenshot({
    path: join(OUT_DIR, `search${suffix}.png`),
    fullPage: true,
  });
  await ctx.close();
}

async function captureAbout(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1500 } });
  const page = await ctx.newPage();
  await setTheme(page);
  await page.goto(`${BASE}/about`);
  await settle(page);
  const suffix = THEME === "dark" ? "-dark" : "";
  await page.screenshot({
    path: join(OUT_DIR, `about${suffix}.png`),
    fullPage: true,
  });
  await ctx.close();
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  try {
    console.log(`base: ${BASE}, theme: ${THEME}, out: ${OUT_DIR}`);
    await captureAskEmpty(browser);
    console.log("  ✓ ask-empty");
    await captureAskAnswer(browser);
    console.log("  ✓ ask-answer");
    await captureSearch(browser);
    console.log("  ✓ search");
    await captureAbout(browser);
    console.log("  ✓ about");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
