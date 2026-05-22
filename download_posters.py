import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
MOVIES_CSV = BASE_DIR / "tmdb_5000_movies.csv"
POSTER_DIR = BASE_DIR / "static" / "posters" / "downloaded"
MANIFEST = POSTER_DIR / "manifest.csv"


def slugify_title(title):
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    return slug or "movie"


def request_url(url, timeout=12):
    request = Request(
        url,
        headers={
            "User-Agent": "MoviePosterDownloader/1.0 (local student project)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def poster_path(movie_id, title, extension):
    return POSTER_DIR / f"{int(movie_id)}-{slugify_title(title)}.{extension}"


def existing_poster(movie_id, title):
    for extension in ("jpg", "jpeg", "png", "webp"):
        path = poster_path(movie_id, title, extension)
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def extension_from_url_or_type(url, content_type):
    lowered = url.lower().split("?")[0]
    if lowered.endswith(".png"):
        return "png"
    if lowered.endswith(".webp"):
        return "webp"
    if "png" in content_type:
        return "png"
    if "webp" in content_type:
        return "webp"
    return "jpg"


def find_tmdb_poster(movie_id):
    html_bytes, _ = request_url(f"https://www.themoviedb.org/movie/{int(movie_id)}")
    html = html_bytes.decode("utf-8", errors="ignore")
    patterns = [
        r'<meta\s+property="og:image"\s+content="([^"]+)"',
        r'https://image\.tmdb\.org/t/p/[^"\']+',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            url = match.group(1) if match.groups() else match.group(0)
            if "image.tmdb.org" in url:
                return url.replace("/w600_and_h900_bestv2/", "/w500/")
    return ""


def find_wikipedia_poster(title):
    candidates = [title, f"{title} (film)"]
    if ":" in title:
        candidates.append(f"{title.replace(':', '')} (film)")

    for candidate in candidates:
        api_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&titles={quote(candidate)}&prop=pageimages"
            "&format=json&pithumbsize=500&origin=*"
        )
        payload_bytes, _ = request_url(api_url)
        payload = json.loads(payload_bytes.decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            source = page.get("thumbnail", {}).get("source")
            if source:
                return source
    return ""


def append_manifest(row):
    is_new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["movie_id", "title", "status", "poster_file", "source_url", "error"],
        )
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def download_one(movie_id, title, source):
    existing = existing_poster(movie_id, title)
    if existing:
        return "skipped", existing, "", ""

    source_url = ""
    if source in ("tmdb", "both"):
        source_url = find_tmdb_poster(movie_id)
    if not source_url and source in ("wikipedia", "both"):
        source_url = find_wikipedia_poster(title)
    if not source_url:
        return "missing", None, "", "No poster URL found"

    image_bytes, content_type = request_url(source_url)
    extension = extension_from_url_or_type(source_url, content_type)
    output_path = poster_path(movie_id, title, extension)
    output_path.write_bytes(image_bytes)
    return "downloaded", output_path, source_url, ""


def main():
    parser = argparse.ArgumentParser(description="Download local poster files for TMDB CSV movies.")
    parser.add_argument("--limit", type=int, default=0, help="Only process this many movies.")
    parser.add_argument("--start", type=int, default=0, help="Start from this zero-based row number.")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds to wait between movies.")
    parser.add_argument(
        "--source",
        choices=["tmdb", "wikipedia", "both"],
        default="tmdb",
        help="Poster source. TMDB uses the movie IDs in your CSV and is usually most accurate.",
    )
    args = parser.parse_args()

    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    movies = pd.read_csv(MOVIES_CSV)
    if "id" not in movies.columns or "title" not in movies.columns:
        raise ValueError("tmdb_5000_movies.csv must include id and title columns.")

    rows = movies[["id", "title"]].dropna().iloc[args.start :]
    if args.limit:
        rows = rows.head(args.limit)

    total = len(rows)
    for number, (_, movie) in enumerate(rows.iterrows(), start=1):
        movie_id = int(movie["id"])
        title = str(movie["title"])
        try:
            status, path, source_url, error = download_one(movie_id, title, args.source)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            status, path, source_url, error = "error", None, "", str(exc)

        append_manifest(
            {
                "movie_id": movie_id,
                "title": title,
                "status": status,
                "poster_file": str(path.relative_to(BASE_DIR)) if path else "",
                "source_url": source_url,
                "error": error,
            }
        )
        print(f"[{number}/{total}] {status}: {title}")
        if args.delay and status != "skipped" and number < total:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
