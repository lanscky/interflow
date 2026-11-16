#!/usr/bin/env python3
"""Build the bundled RDC higher-education catalogue from the official registry."""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen


BASE_URL = "https://www.re.minesursi.gouv.cd"
LIST_URL = f"{BASE_URL}/universites-instituts.php?page={{page}}"
TOTAL_PAGES = 130
CARD_MARKER = '<div class="card bg-white shadow-xl card-hover"'


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split()).strip()


def match(pattern: str, value: str) -> str:
    result = re.search(pattern, value, flags=re.DOTALL | re.IGNORECASE)
    return clean(result.group(1)) if result else ""


def parse_page(document: str) -> list[dict[str, object]]:
    schools: list[dict[str, object]] = []
    for block in document.split(CARD_MARKER)[1:]:
        registry_id = match(r'etablissement\.php\?id=(\d+)', block)
        name = match(r'<h3[^>]*>(.*?)</h3>', block)
        if not registry_id or not name:
            continue

        sigle = match(r'badge-primary badge-outline mb-2[^>]*>(.*?)</div>', block)
        ownership = match(r'<div class="badge badge-(?:warning|success)[^>]*>(.*?)</div>', block)
        location = match(r'text-sm text-gray-600 mt-2 space-y-1[^>]*>\s*<div>(.*?)</div>', block)
        province, separator, territory = location.partition(" / ")
        if not separator:
            province, territory = location, ""

        schools.append({
            "registry_id": int(registry_id),
            "name": name,
            "sigle": sigle,
            "category": match(r'Catégorie\s*:\s*<span[^>]*>(.*?)</span>', block),
            "ownership": ownership,
            "territory": territory,
            "province": province,
            "approval_status": match(r'État d[’\']agrément\s*:\s*<span[^>]*>(.*?)</span>', block),
            "source_url": f"{BASE_URL}/etablissement.php?id={registry_id}",
            "is_active": True,
        })
    return schools


def fetch_page(page: int, insecure: bool = False, attempts: int = 3) -> list[dict[str, object]]:
    for attempt in range(1, attempts + 1):
        try:
            request = Request(
                LIST_URL.format(page=page),
                headers={"User-Agent": "TotindaSchoolCatalogue/1.0 (+https://totinda.com)"},
            )
            context = ssl._create_unverified_context() if insecure else None
            with urlopen(request, timeout=30, context=context) as response:
                return parse_page(response.read().decode("utf-8", errors="replace"))
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(attempt)
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "appstage" / "data" / "rdc_schools.json",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Désactive explicitement la vérification TLS si le registre officiel présente une chaîne invalide.",
    )
    args = parser.parse_args()

    schools_by_id: dict[int, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as executor:
        futures = {
            executor.submit(fetch_page, page, args.insecure): page
            for page in range(1, TOTAL_PAGES + 1)
        }
        for future in as_completed(futures):
            page = futures[future]
            rows = future.result()
            if not rows:
                raise RuntimeError(f"La page {page} du registre ne contient aucun établissement.")
            schools_by_id.update({int(row["registry_id"]): row for row in rows})

    schools = sorted(schools_by_id.values(), key=lambda row: (str(row["name"]).casefold(), int(row["registry_id"])))
    if len(schools) < 1500:
        raise RuntimeError(f"Catalogue incomplet : seulement {len(schools)} établissements extraits.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schools, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(schools)} établissements écrits dans {args.output}")


if __name__ == "__main__":
    main()
