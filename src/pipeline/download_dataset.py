"""
Read wikiarch.json and download assets (images + Wikipedia descriptions) to a given directory.

Follows the Wikimedia robot policy: https://wikitech.wikimedia.org/wiki/Robot_policy
- Identifies via User-Agent; uses gzip for HTML; respects 429 Retry-After and 5xx pause.
- Media: sequential requests, configurable delay (min 1s). Prefer --thumbnail when possible.

Usage:
  uv run python -m src.pipeline.download_dataset <path_to_wikiarch.json> <output_dir> [options]
  uv run python -m src.pipeline.download_dataset data/wikiarch.json data/wikiarch/raw --limit 10

JSON must be a list of items with: item_name, item_id, images (list of page_url, image_id, thumbnail, ...).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    import wikipediaapi
except ImportError:
    wikipediaapi = None  # type: ignore[assignment]

# Robot policy: https://wikitech.wikimedia.org/wiki/Robot_policy
# User-Agent must identify the bot (project/version + contact per WMF User-Agent policy).
USER_AGENT = "ArchLogicRAG/1.0 (https://github.com/danruili/ArchLogicRAG; research dataset; Python requests)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}
# HTML/API requests: request gzip to reduce bandwidth (policy: "Default to gzip").
REQUEST_HEADERS_HTML = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
# Media (images): policy says gzip not necessary for media; no extra headers.
PAUSE_5XX_SECONDS = 900  # Policy: "Pause crawling for at least 15 minutes if you receive a 5xx"
MIN_DELAY_SECONDS = 1.0   # Policy: "delay between requests of at least 1 second" for resources


def _handle_http_backoff(resp: requests.Response) -> None:
    """Respect robot policy: 429 Retry-After and 5xx 15-minute pause. Raises after sleeping."""
    if resp.status_code == 429:
        delay = 60
        if "Retry-After" in resp.headers:
            try:
                delay = int(resp.headers["Retry-After"])
            except ValueError:
                pass
        print(f"  429 Too Many Requests; waiting {delay}s (Retry-After)...")
        time.sleep(delay)
        resp.raise_for_status()
    if 500 <= resp.status_code < 600:
        print(f"  {resp.status_code} server error; pausing {PAUSE_5XX_SECONDS}s per robot policy...")
        time.sleep(PAUSE_5XX_SECONDS)
        resp.raise_for_status()


def _sanitize_dirname(name: str) -> str:
    """Safe directory name from item_name."""
    return re.sub(r'[/\\:*?"<>|]', "_", name.strip()) or "unnamed"


def thumbnail_to_full_url(thumbnail_url: str) -> str | None:
    """Convert Wikimedia Commons thumbnail URL to full-size image URL."""
    if "/thumb/" not in thumbnail_url or "upload.wikimedia.org" not in thumbnail_url:
        return None
    try:
        parts = thumbnail_url.split("/thumb/", 1)
        if len(parts) != 2:
            return None
        base, rest = parts
        path_parts = rest.split("/")
        if len(path_parts) < 4:
            return None
        hash1, hash2, filename = path_parts[0], path_parts[1], path_parts[2]
        return f"{base}/{hash1}/{hash2}/{filename}"
    except Exception:
        return None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _get_image_url_from_page(page_url: str) -> str:
    """Resolve Commons page URL to direct image URL. Uses gzip for HTML (robot policy)."""
    resp = requests.get(page_url, headers=REQUEST_HEADERS_HTML, timeout=30)
    _handle_http_backoff(resp)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    link = soup.select_one("#mw-content-text div.fullMedia p a, .fullMedia p a")
    if not link or not link.get("href"):
        raise ValueError(f"No image link found on {page_url}")
    href = link["href"]
    if href.startswith("//"):
        href = "https:" + href
    return href


def _image_url_for(
    image: dict,
    use_thumbnail_derivation: bool = True,
    thumbnails_only: bool = False,
) -> str:
    """Get image URL. If thumbnails_only, return thumbnail URL as-is; else full-size (derive or scrape)."""
    if thumbnails_only and image.get("thumbnail"):
        return image["thumbnail"]
    if use_thumbnail_derivation and image.get("thumbnail"):
        full = thumbnail_to_full_url(image["thumbnail"])
        if full:
            return full
    return _get_image_url_from_page(image["page_url"])


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _download_image(image_url: str, save_path: Path) -> None:
    """Download image to save_path. No gzip for media (robot policy). Concurrency 1 (sequential)."""
    resp = requests.get(image_url, headers=REQUEST_HEADERS, stream=True, timeout=60)
    _handle_http_backoff(resp)
    resp.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


def _scale_image(img: Image.Image, max_dim: int = 1440) -> Image.Image:
    """Scale image preserving aspect ratio; larger side at most max_dim."""
    w, h = img.size
    if w <= max_dim and h <= max_dim:
        return img
    if w >= h:
        new_w = max_dim
        new_h = int(round(h * new_w / w))
    else:
        new_h = max_dim
        new_w = int(round(w * new_h / h))
    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _ensure_rgb_for_jpeg(img: Image.Image) -> Image.Image:
    """Convert to RGB so we can save as JPEG; composite RGBA/P onto white."""
    if img.mode == "RGB":
        return img
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    if img.mode == "P":
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")


def _extract_description(item_name: str) -> str:
    """Fetch Wikipedia article text for item_name."""
    if not wikipediaapi:
        return f"(Install wikipedia-api for description of '{item_name}')\n"
    wiki = wikipediaapi.Wikipedia(
        user_agent=USER_AGENT,
        language="en",
        extract_format=wikipediaapi.ExtractFormat.WIKI,
    )
    page = wiki.page(item_name)
    return page.text if page.exists() else f"(No Wikipedia page for '{item_name}')\n"


def _download_item(
    meta: dict,
    output_dir: Path,
    *,
    scale: bool = True,
    max_dim: int = 1440,
    skip_existing: bool = True,
    dry_run: bool = False,
    use_thumbnail_derivation: bool = True,
    thumbnails_only: bool = False,
    delay_seconds: float = 1.0,
) -> None:
    """Download images and description for one item."""
    item_name = meta["item_name"]
    item_dir = output_dir / _sanitize_dirname(item_name)
    description_file = item_dir / "description.txt"

    if skip_existing and description_file.exists():
        return

    if dry_run:
        print(f"[dry-run] {item_name}")
        return

    item_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading: {item_name}")

    for image in meta.get("images", []):
        image_id = image.get("image_id", "unknown")
        try:
            image_url = _image_url_for(
                image,
                use_thumbnail_derivation=use_thumbnail_derivation,
                thumbnails_only=thumbnails_only,
            )
        except Exception as e:
            print(f"  Skip {image_id}: {e}")
            continue

        ext = "jpg"
        if "." in image_url.split("/")[-1].split("?")[0]:
            ext = image_url.split(".")[-1].split("?")[0].lower() or "jpg"
        safe_ext = "jpg" if ext in ("jpg", "jpeg", "png", "gif", "webp") else "jpg"
        save_path = item_dir / f"{image_id}.{safe_ext}"

        if skip_existing and save_path.exists():
            continue

        time.sleep(delay_seconds)
        try:
            _download_image(image_url, save_path)
        except Exception as e:
            print(f"  Failed {image_id}: {e}")
            continue

        if scale:
            try:
                img = Image.open(save_path)
                img = _scale_image(img, max_dim=max_dim)
                if save_path.suffix.lower() in (".jpg", ".jpeg"):
                    img = _ensure_rgb_for_jpeg(img)
                img.save(save_path, quality=90)
            except Exception as e:
                print(f"  Scale failed {save_path}: {e}")

    with open(description_file, "w", encoding="utf-8") as f:
        f.write(_extract_description(item_name))


def download_dataset(
    json_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
    scale: bool = True,
    max_dim: int = 1440,
    skip_existing: bool = True,
    dry_run: bool = False,
    use_thumbnail_derivation: bool = True,
    thumbnails_only: bool = False,
    delay_seconds: float = 1.0,
) -> None:
    """
    Read wikiarch.json and download all assets to output_dir.

    Each item gets a subdirectory (sanitized item_name) with:
    - {image_id}.jpg (or correct extension)
    - description.txt (Wikipedia text)
    """
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        raise ValueError("JSON must be a list of items")

    if limit is not None:
        items = items[:limit]

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for meta in items:
        _download_item(
            meta,
            output_dir,
            scale=scale,
            max_dim=max_dim,
            skip_existing=skip_existing,
            dry_run=dry_run,
            use_thumbnail_derivation=use_thumbnail_derivation,
            thumbnails_only=thumbnails_only,
            delay_seconds=delay_seconds,
        )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Read wikiarch.json and download assets to a given directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "json_path",
        type=Path,
        nargs="?",
        default=root / "data" / "wikiarch.json",
        help="Path to wikiarch.json",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        default=root / "data" / "wikiarch" / "raw",
        help="Directory to save assets (per-item subdirs with images + description.txt)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max number of items")
    parser.add_argument("--no-scale", action="store_true", help="Do not scale images")
    parser.add_argument("--max-dim", type=int, default=1440, help="Max dimension when scaling")
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not download")
    parser.add_argument(
        "--scrape-url",
        action="store_true",
        help="Always scrape Commons page for image URL (slower)",
    )
    parser.add_argument(
        "--thumbnail",
        action="store_true",
        help="Download thumbnail images instead of full-size (uses thumbnail URL from JSON as-is)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help=f"Seconds between requests (min {MIN_DELAY_SECONDS}s per robot policy)",
    )

    args = parser.parse_args()
    if not args.json_path.exists():
        raise SystemExit(f"JSON not found: {args.json_path}")
    if args.delay < MIN_DELAY_SECONDS:
        raise SystemExit(
            f"Delay must be at least {MIN_DELAY_SECONDS}s per Wikimedia robot policy; got {args.delay}"
        )

    download_dataset(
        args.json_path.resolve(),
        args.output_dir.resolve(),
        limit=args.limit,
        scale=not args.no_scale,
        max_dim=args.max_dim,
        skip_existing=not args.force,
        dry_run=args.dry_run,
        use_thumbnail_derivation=not args.scrape_url,
        thumbnails_only=args.thumbnail,
        delay_seconds=args.delay,
    )
    print("Done.")


if __name__ == "__main__":
    main()
