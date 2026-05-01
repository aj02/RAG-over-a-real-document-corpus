#!/usr/bin/env node
/**
 * Browser-based corpus downloader.
 *
 * Why this exists alongside scripts/download_corpus.py: SEBI and RBI both
 * front their public document index pages with a JavaScript bot challenge
 * that returns the same anti-automation HTML to a plain httpx/curl request,
 * regardless of the User-Agent. A real browser executes the challenge
 * script and is then redirected to (or shown a link to) the actual PDF.
 *
 * This script drives a headless Chromium via Playwright:
 *   1. open the manifest URL
 *   2. wait for the JS challenge to clear (network idle)
 *   3. find the first link whose href ends in .pdf or whose text says PDF
 *   4. follow it inside the same browser context (so cookies persist) and
 *      save the bytes
 *   5. otherwise, capture the document via Chromium's print-to-PDF
 *      (acceptable fallback — preserves the visible regulation text).
 *
 * Run from the repo root with:
 *
 *   cd web && pnpm install                         # one-time
 *   cd web && npx playwright install chromium      # one-time
 *   node ../scripts/download_via_browser.mjs
 *
 * Or, since Playwright's package lives under web/, you can invoke from
 * inside web/ directly:
 *
 *   cd web && node ../scripts/download_via_browser.mjs
 */

import { chromium } from "playwright";
import { mkdir, readFile, writeFile, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const MANIFEST = join(REPO_ROOT, "data", "corpus_manifest.json");
const OUT_DIR = join(REPO_ROOT, "data", "pdfs");

// Treat anything below this as a JS-challenge page or an error stub.
const MIN_PDF_BYTES = 60 * 1024;
const PDF_MAGIC = "%PDF-";

const args = process.argv.slice(2);
const onlyDocs = new Set();
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--doc" && args[i + 1]) {
    onlyDocs.add(args[++i]);
  }
}

function isPdfBytes(buf) {
  return buf && buf.length > 4 && buf.slice(0, 5).toString() === PDF_MAGIC;
}

async function fileSize(p) {
  try {
    const s = await stat(p);
    return s.size;
  } catch {
    return -1;
  }
}

async function findPdfHref(page) {
  // Strongest signal first: an <a href="...pdf"> in the page DOM.
  const direct = await page.evaluate(() => {
    const anchors = Array.from(document.querySelectorAll("a"));
    const pdfA = anchors.find((a) => /\.pdf(\?|#|$)/i.test(a.href));
    if (pdfA) return pdfA.href;
    // RBI sometimes labels the link as "PDF" without a .pdf extension.
    const labelled = anchors.find((a) =>
      /\bpdf\b/i.test(a.textContent ?? ""),
    );
    return labelled?.href ?? null;
  });
  return direct ?? null;
}

async function downloadOne(browser, entry) {
  const outPath = join(OUT_DIR, `${entry.doc_id}.pdf`);
  const existing = await fileSize(outPath);
  if (existing >= MIN_PDF_BYTES) {
    console.log(`  ✓ ${entry.doc_id}  already present (${existing} bytes)`);
    return true;
  }

  const ctx = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    acceptDownloads: true,
    viewport: { width: 1280, height: 1600 },
    extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" },
  });
  const page = await ctx.newPage();
  console.log(`-> ${entry.doc_id}: ${entry.source_url}`);

  try {
    await page.goto(entry.source_url, {
      waitUntil: "networkidle",
      timeout: 45_000,
    });
    // Some JS challenges add another second or two of work after networkidle.
    await page.waitForTimeout(1500);

    const status = page.url();
    if (status.toLowerCase().endsWith(".pdf")) {
      // The page itself is a PDF; fetch its bytes via the browser context.
      const buf = Buffer.from(
        await ctx.request.get(status).then((r) => r.body()),
      );
      if (!isPdfBytes(buf) || buf.length < MIN_PDF_BYTES) {
        console.log(`  ✗ direct PDF was small/non-PDF (${buf.length} bytes)`);
        return false;
      }
      await writeFile(outPath, buf);
      console.log(`  ✓ saved ${buf.length} bytes`);
      return true;
    }

    const pdfHref = await findPdfHref(page);
    if (!pdfHref) {
      console.log("  ✗ no PDF link discoverable on the page");
      return false;
    }
    console.log(`   pdf link: ${pdfHref}`);

    // Fetch the PDF using the browser context (cookies + UA persist).
    const resp = await ctx.request.get(pdfHref);
    if (resp.status() !== 200) {
      console.log(`  ✗ HTTP ${resp.status()} fetching PDF`);
      return false;
    }
    const buf = Buffer.from(await resp.body());
    if (!isPdfBytes(buf) || buf.length < MIN_PDF_BYTES) {
      console.log(
        `  ✗ response not a PDF or too small (${buf.length} bytes, magic=${buf.slice(0, 5).toString()})`,
      );
      return false;
    }
    await writeFile(outPath, buf);
    console.log(`  ✓ saved ${buf.length} bytes`);
    return true;
  } catch (err) {
    console.log(`  ✗ ${err.name}: ${err.message}`);
    return false;
  } finally {
    await ctx.close();
  }
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const manifest = JSON.parse(await readFile(MANIFEST, "utf-8"));
  let entries = manifest.documents;
  if (onlyDocs.size > 0) {
    entries = entries.filter((d) => onlyDocs.has(d.doc_id));
  }

  console.log(`manifest: ${manifest.documents.length} documents`);
  console.log(`will attempt: ${entries.length}`);
  console.log(`out_dir: ${OUT_DIR}`);
  console.log();

  const browser = await chromium.launch({ headless: true });
  const succeeded = [];
  const failed = [];
  try {
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i];
      process.stdout.write(`[${i + 1}/${entries.length}] `);
      const ok = await downloadOne(browser, entry);
      (ok ? succeeded : failed).push(entry.doc_id);
    }
  } finally {
    await browser.close();
  }

  console.log();
  console.log(`summary: ${succeeded.length}/${entries.length} succeeded`);
  if (failed.length) {
    console.log(`failed:  ${JSON.stringify(failed)}`);
  }
  process.exit(failed.length === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
