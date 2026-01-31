"""I/O helpers for SnapMatch.

This module handles:
- cache read/write (optional)
- safe copying/linking files into the output folder
- report generation (CSV and optional XLSX)
"""

from __future__ import annotations

import csv
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .hashing import ImageHash


@dataclass(frozen=True)
class CacheEntry:
    """One cached hash entry keyed by absolute file path."""

    mtime_ns: int
    size: int
    dhash: int


def load_cache(cache_path: Path) -> Dict[str, CacheEntry]:
    """Load a hash cache from CSV.

    The cache is keyed by absolute path string. Rows that can't be parsed
    are skipped.

    Cache schema:
        path, mtime_ns, size, dhash

    Parameters
    ----------
    cache_path:
        Path to the cache CSV.

    Returns
    -------
    dict[str, CacheEntry]
        A map from absolute path to CacheEntry.
    """

    cache: Dict[str, CacheEntry] = {}
    if not cache_path.exists():
        return cache

    try:
        with cache_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    p = row["path"]
                    cache[p] = CacheEntry(
                        mtime_ns=int(row["mtime_ns"]),
                        size=int(row["size"]),
                        dhash=int(row["dhash"]),
                    )
                except Exception:
                    continue
    except Exception:
        return {}

    return cache


def save_cache(cache_path: Path, hashes: Iterable[ImageHash]) -> None:
    """Save a hash cache to CSV.

    Parameters
    ----------
    cache_path:
        Output CSV path.
    hashes:
        Iterable of ImageHash objects.
    """

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "mtime_ns", "size", "dhash"])
        for h in hashes:
            st = h.path.stat()
            writer.writerow([str(h.path), st.st_mtime_ns, st.st_size, int(h.dhash)])


def unique_destination(out_dir: Path, desired_name: str) -> Path:
    """Return a destination path in `out_dir` that won't overwrite an existing file.

    If `desired_name` already exists, appends a suffix like:
        photo.jpg -> photo__2.jpg, photo__3.jpg, ...
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / desired_name
    if not dst.exists():
        return dst

    stem = dst.stem
    suffix = dst.suffix
    n = 2
    while True:
        cand = out_dir / f"{stem}__{n}{suffix}"
        if not cand.exists():
            return cand
        n += 1


def copy_or_link(src: Path, dst: Path, mode: str = "copy") -> None:
    """Copy or link a file from src to dst.

    Parameters
    ----------
    src:
        Source file path.
    dst:
        Destination path.
    mode:
        "copy" (default), "hardlink", or "symlink".

    Notes
    -----
    - Hardlinks require same filesystem/volume.
    - Symlinks on Windows may require developer mode/admin privileges.
    """

    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    if mode == "hardlink":
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
        return
    if mode == "symlink":
        if dst.exists():
            dst.unlink()
        os.symlink(src, dst)
        return
    raise ValueError(f"Unknown mode: {mode!r}. Use copy|hardlink|symlink.")


def write_mapping_csv(rows: List[dict], out_csv: Path) -> None:
    """Write the mapping report as CSV."""

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0].keys()) if rows else ["edited", "raw_match", "distance", "status", "copied_to"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def write_mapping_xlsx(rows: List[dict], out_xlsx: Path) -> bool:
    """Write the mapping report as XLSX.

    Returns False if openpyxl isn't installed.
    """

    try:
        from openpyxl import Workbook  # type: ignore
    except Exception:
        return False

    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "mapping"

    headers = list(rows[0].keys()) if rows else ["edited", "raw_match", "distance", "status", "copied_to"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])

    wb.save(out_xlsx)
    return True
