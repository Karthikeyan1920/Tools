"""Hashing utilities for SnapMatch.

SnapMatch uses a perceptual **difference hash** (dHash) to represent an image as
a 64-bit fingerprint. It works well for "same photo, different filename" cases,
and is usually robust to mild resizing/compression.

Implementation notes
--------------------
The dHash algorithm:

1) Convert to grayscale
2) Resize to 9x8 pixels
3) Compare adjacent pixels horizontally:
   for each row, set bit=1 if pixel[x+1] > pixel[x] else 0
4) Pack the 8*8 comparisons into a 64-bit integer

The Hamming distance between two hashes is the number of different bits.
Smaller distance => more visually similar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence

import os

from PIL import Image


# Common extensions in real-world photo pipelines. Add more if you need.
DEFAULT_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".jfif",
}


@dataclass(frozen=True)
class ImageHash:
    """A computed dHash for a specific image file path."""

    path: Path
    dhash: int  # 64-bit integer


def iter_images(root: Path, exts: Sequence[str] = tuple(DEFAULT_EXTS)) -> Iterator[Path]:
    """Recursively yield image file paths under *root*.

    Parameters
    ----------
    root:
        Folder to scan.
    exts:
        File extensions to include. Compared case-insensitively.

    Yields
    ------
    Path
        Paths to image files.
    """

    root = root.expanduser().resolve()
    exts_lc = {e.lower() for e in exts}
    for folder, _, files in os.walk(root):
        for name in files:
            ext = Path(name).suffix.lower()
            if ext in exts_lc:
                yield Path(folder) / name


def dhash64(path: Path) -> Optional[int]:
    """Compute a 64-bit dHash for an image.

    Returns ``None`` if the file can't be opened/decoded as an image.

    Parameters
    ----------
    path:
        Path to an image file.

    Returns
    -------
    Optional[int]
        64-bit dHash as an integer, or None on failure.
    """

    try:
        with Image.open(path) as img:
            # Convert to grayscale and resize to 9x8.
            img = img.convert("L").resize((9, 8), resample=Image.Resampling.BILINEAR)
            # Pillow returns a flat sequence of length 72.
            px = list(img.getdata())

        # Build 64 bits from 8 rows × 8 comparisons.
        h = 0
        bit = 1 << 63  # MSB first (direction doesn't matter for distance)
        for row in range(8):
            base = row * 9
            for col in range(8):
                left = px[base + col]
                right = px[base + col + 1]
                if right > left:
                    h |= bit
                bit >>= 1
        return h
    except Exception:
        return None


def hamming_distance(a: int, b: int) -> int:
    """Compute the Hamming distance between two 64-bit hashes.

    This is the number of different bits in ``a`` and ``b``.

    Parameters
    ----------
    a, b:
        Hashes as integers.

    Returns
    -------
    int
        Number of differing bits.
    """

    x = a ^ b
    # Python 3.8+ has int.bit_count() (fast, implemented in C).
    return x.bit_count() if hasattr(int, "bit_count") else bin(x).count("1")
