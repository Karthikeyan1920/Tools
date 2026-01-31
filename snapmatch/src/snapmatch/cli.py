"""SnapMatch CLI.

This is the entry point used by:
- `python -m snapmatch`
- the console script `snapmatch` (installed via pyproject.toml)
- PyInstaller builds (`pyinstaller -m snapmatch.cli`)

Example
-------
snapmatch --raw "/data/raw" --edited "/data/edited" --out "/data/out"

Design goals
------------
- Cross-platform (Windows/macOS/Linux)
- No hard-coded paths: everything is passed via CLI arguments
- Practical defaults and a CSV report that is easy to audit
"""

from __future__ import annotations

import argparse
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Sequence

from tqdm import tqdm

from .hashing import ImageHash, dhash64, iter_images
from .matching import find_best_match
from .io_utils import (
    copy_or_link,
    load_cache,
    save_cache,
    unique_destination,
    write_mapping_csv,
    write_mapping_xlsx,
)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        prog="snapmatch",
        description=(
            "Match edited images to closest raw originals using perceptual dHash "
            "and copy matches into an output folder."
        ),
    )
    p.add_argument(
        "--raw",
        required=True,
        type=Path,
        help="Path to raw/original images folder (scanned recursively).",
    )
    p.add_argument(
        "--edited",
        required=True,
        type=Path,
        help="Path to edited images folder (scanned recursively).",
    )
    p.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output folder to place matched raw originals.",
    )
    p.add_argument(
        "--max-distance",
        type=int,
        default=3,
        help=(
            "Maximum Hamming distance allowed for a match (default: 3). "
            "Larger => fewer false negatives, more false positives."
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "Number of worker processes for hashing raw images (default: 0 = auto). "
            "Use 1 to disable multiprocessing."
        ),
    )
    p.add_argument(
        "--mode",
        choices=["copy", "hardlink", "symlink"],
        default="copy",
        help="How to place matched files into the output folder (default: copy).",
    )
    p.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Optional CSV cache for raw hashes. If omitted, uses <out>/snapmatch_cache.csv.",
    )
    p.add_argument(
        "--report-xlsx",
        action="store_true",
        help="Also write mapping.xlsx (requires openpyxl).",
    )
    p.add_argument(
        "--preserve-raw-subdirs",
        action="store_true",
        help="Preserve the raw folder subdirectory structure inside the output folder.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not copy/link files; only generate the report.",
    )
    return p.parse_args(argv)


def _hash_path_worker(p: Path) -> Optional[ImageHash]:
    """Multiprocessing worker: compute dhash for a single image path.

    This function is top-level so it can be pickled on Windows.
    """
    h = dhash64(p)
    if h is None:
        return None
    return ImageHash(path=p, dhash=h)


def _hash_raw_images(raw_dir: Path, cache_path: Path, workers: int) -> List[ImageHash]:
    """Compute (or reuse) hashes for all raw images.

    A cache is used for speed on re-runs. Cache entries are reused when
    the file's (mtime_ns, size) are unchanged.
    """
    raw_dir = raw_dir.expanduser().resolve()
    cache_path = cache_path.expanduser().resolve()

    cache = load_cache(cache_path)
    paths = list(iter_images(raw_dir))

    # Reuse what we can from cache; compute missing ones.
    reuse: List[ImageHash] = []
    todo: List[Path] = []
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        key = str(p.resolve())
        ce = cache.get(key)
        if ce and ce.mtime_ns == st.st_mtime_ns and ce.size == st.st_size:
            reuse.append(ImageHash(path=p.resolve(), dhash=ce.dhash))
        else:
            todo.append(p.resolve())

    out: List[ImageHash] = []
    out.extend(reuse)

    if not todo:
        return out

    # If workers <= 1, hash in-process.
    if workers == 1:
        for p in tqdm(todo, desc="Hashing raw", unit="img"):
            r = _hash_path_worker(p)
            if r is not None:
                out.append(r)
        save_cache(cache_path, out)
        return out

    max_workers = None if workers == 0 else max(1, workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as ex:
        for r in tqdm(ex.map(_hash_path_worker, todo), total=len(todo), desc="Hashing raw", unit="img"):
            if r is not None:
                out.append(r)

    save_cache(cache_path, out)
    return out


def _hash_edited_images(edited_dir: Path) -> List[ImageHash]:
    """Hash all edited images (no cache by default)."""
    edited_dir = edited_dir.expanduser().resolve()
    paths = list(iter_images(edited_dir))
    out: List[ImageHash] = []
    for p in tqdm(paths, desc="Hashing edited", unit="img"):
        h = dhash64(p)
        if h is None:
            continue
        out.append(ImageHash(path=p.resolve(), dhash=h))
    return out


def _relative_under(root: Path, path: Path) -> Path:
    """Compute `path` relative to `root`, falling back to basename if not possible."""
    try:
        return path.resolve().relative_to(root.resolve())
    except Exception:
        return Path(path.name)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run SnapMatch.

    Returns
    -------
    int
        Process exit code (0 success).
    """
    args = _parse_args(argv)

    raw_dir: Path = args.raw
    edited_dir: Path = args.edited
    out_dir: Path = args.out

    raw_dir = raw_dir.expanduser().resolve()
    edited_dir = edited_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()

    if not raw_dir.exists() or not raw_dir.is_dir():
        raise SystemExit(f"--raw must be an existing folder: {raw_dir}")
    if not edited_dir.exists() or not edited_dir.is_dir():
        raise SystemExit(f"--edited must be an existing folder: {edited_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = args.cache if args.cache is not None else (out_dir / "snapmatch_cache.csv")

    # 1) Hash raw
    raw_hashes = _hash_raw_images(raw_dir, cache_path, workers=int(args.workers))
    if not raw_hashes:
        raise SystemExit("No readable raw images found. Check extensions and permissions.")

    # 2) Hash edited
    edited_hashes = _hash_edited_images(edited_dir)
    if not edited_hashes:
        raise SystemExit("No readable edited images found. Check extensions and permissions.")

    # 3) Match + copy
    mapping_rows: List[dict] = []

    for eh in tqdm(edited_hashes, desc="Matching", unit="img"):
        res = find_best_match(eh, raw_hashes, max_distance=int(args.max_distance))

        copied_to = ""
        if res.status == "matched" and res.matched_raw_path is not None:
            raw_path = res.matched_raw_path

            if args.preserve_raw_subdirs:
                rel = _relative_under(raw_dir, raw_path)
                dst_dir = out_dir / rel.parent
                dst = unique_destination(dst_dir, rel.name)
            else:
                dst = unique_destination(out_dir, raw_path.name)

            copied_to = str(dst)

            if not args.dry_run:
                copy_or_link(raw_path, dst, mode=args.mode)

        mapping_rows.append(
            {
                "edited": str(res.edited_path),
                "raw_match": str(res.matched_raw_path) if res.matched_raw_path else "",
                "distance": res.distance if res.distance is not None else "",
                "status": res.status,
                "copied_to": copied_to,
            }
        )

    # 4) Reports
    out_csv = out_dir / "mapping.csv"
    write_mapping_csv(mapping_rows, out_csv)

    if args.report_xlsx:
        out_xlsx = out_dir / "mapping.xlsx"
        ok = write_mapping_xlsx(mapping_rows, out_xlsx)
        if not ok:
            print(
                "Note: openpyxl is not installed, so mapping.xlsx was not created. "
                "Install with: pip install snapmatch[report]"
            )

    matched = sum(1 for r in mapping_rows if r["status"] == "matched")
    no_match = len(mapping_rows) - matched

    print(f"\nDone. Matched: {matched} | Not matched: {no_match}")
    print(f"Report: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
