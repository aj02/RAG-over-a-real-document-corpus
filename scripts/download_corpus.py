"""Download every PDF referenced in data/corpus_manifest.json.

The script is HTML-aware: if the source URL serves text/html, we look for the
first ``<a href="...pdf">`` link on the page and follow it. SEBI and RBI both
publish documents through HTML landing pages that link to the actual PDF, so
this lets the manifest stay stable when the underlying PDF filename changes.

Usage:
    python scripts/download_corpus.py             # download all
    python scripts/download_corpus.py --doc SEBI-MC-MF-2024
    python scripts/download_corpus.py --validate  # HEAD requests only
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

from app.ingestion.manifest import Manifest, ManifestEntry, load_manifest

PDF_LINK_RE = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.IGNORECASE)

# A regulator-friendly browser UA. RBI and SEBI both run bot-protection that
# rejects bare httpx/curl signatures and serves a JS challenge page instead.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/pdf;q=0.8,image/avif,image/webp,*/*;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# Pages that look like bot/JS challenges rather than the document. We refuse
# to "save" these as PDFs even if the server returns 200 OK.
_CHALLENGE_MARKERS = (
    "Please enable JavaScript",
    "support_id",
    "captcha",
    "bobcmn",
)


def _is_challenge_page(text: str) -> bool:
    sample = text[:4000].lower()
    return any(m.lower() in sample for m in _CHALLENGE_MARKERS)


def _resolve_pdf_url(url: str, *, client: httpx.Client) -> str | None:
    """Follow the URL; if it's HTML, return the first PDF href on the page."""
    try:
        r = client.get(url, follow_redirects=True, timeout=30.0)
    except httpx.RequestError as e:
        print(f"  ✗ network error fetching {url}: {e}", file=sys.stderr)
        return None
    if r.status_code != 200:
        print(f"  ✗ HTTP {r.status_code} for {url}", file=sys.stderr)
        return None

    content_type = (r.headers.get("content-type") or "").lower()
    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        # save bytes to a tempfile by returning the resolved URL itself.
        return str(r.url)

    if "html" in content_type:
        if _is_challenge_page(r.text):
            print(
                f"  ✗ bot/JS challenge page (not the document): {url}",
                file=sys.stderr,
            )
            return None
        match = PDF_LINK_RE.search(r.text)
        if match:
            pdf_url = match.group(1)
            if pdf_url.startswith("/"):
                pdf_url = f"{r.url.scheme}://{r.url.host}{pdf_url}"
            elif not pdf_url.startswith("http"):
                pdf_url = str(r.url.join(pdf_url))
            return pdf_url
        print(f"  ✗ no PDF link found on HTML page: {url}", file=sys.stderr)
        return None

    print(
        f"  ✗ unexpected content-type {content_type!r} for {url}",
        file=sys.stderr,
    )
    return None


def download_one(
    entry: ManifestEntry, *, out_dir: Path, client: httpx.Client, validate_only: bool
) -> bool:
    out_path = out_dir / f"{entry.doc_id}.pdf"
    if out_path.exists() and not validate_only:
        print(f"  ✓ {entry.doc_id} already present, skipping")
        return True

    print(f"-> {entry.doc_id}: {entry.source_url}")
    pdf_url = _resolve_pdf_url(str(entry.source_url), client=client)
    if pdf_url is None:
        return False

    if validate_only:
        try:
            r = client.head(pdf_url, follow_redirects=True, timeout=15.0)
            if r.status_code in (200, 206):
                print(f"  ✓ ok ({r.status_code}) -> {pdf_url}")
                return True
            print(f"  ✗ HEAD {r.status_code} -> {pdf_url}", file=sys.stderr)
            return False
        except httpx.RequestError as e:
            print(f"  ✗ HEAD failed: {e}", file=sys.stderr)
            return False

    try:
        with client.stream("GET", pdf_url, follow_redirects=True, timeout=120.0) as r:
            if r.status_code != 200:
                print(f"  ✗ HTTP {r.status_code} for {pdf_url}", file=sys.stderr)
                return False
            tmp = out_path.with_suffix(".pdf.tmp")
            with tmp.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
            tmp.replace(out_path)
        print(f"  ✓ saved {out_path}")
        return True
    except httpx.RequestError as e:
        print(f"  ✗ download failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="data/corpus_manifest.json",
        help="path to manifest JSON",
    )
    parser.add_argument(
        "--out-dir",
        default="data/pdfs",
        help="where to write PDFs",
    )
    parser.add_argument(
        "--doc",
        action="append",
        help="restrict to specific doc_ids (may be passed multiple times)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="HEAD-check URLs only — do not download",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="seconds to wait between requests (be polite)",
    )
    args = parser.parse_args()

    manifest: Manifest = load_manifest(Path(args.manifest))
    entries = manifest.documents
    if args.doc:
        wanted = set(args.doc)
        entries = [e for e in entries if e.doc_id in wanted]
        missing = wanted - {e.doc_id for e in entries}
        if missing:
            print(f"unknown doc_ids: {sorted(missing)}", file=sys.stderr)
            return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed: list[str] = []
    with httpx.Client(headers=DEFAULT_HEADERS) as client:
        for i, entry in enumerate(entries, 1):
            print(f"[{i}/{len(entries)}]", end=" ")
            if download_one(
                entry, out_dir=out_dir, client=client, validate_only=args.validate
            ):
                ok += 1
            else:
                failed.append(entry.doc_id)
            if i < len(entries) and args.sleep > 0:
                time.sleep(args.sleep)

    print()
    print(f"summary: {ok}/{len(entries)} succeeded")
    if failed:
        print(f"failed:  {failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
