"""Matching logic for SnapMatch.

Given:
- a list of raw/original image hashes, and
- a list of edited image hashes

We find, for each edited image, the raw image with the smallest Hamming distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .hashing import ImageHash, hamming_distance


@dataclass(frozen=True)
class MatchResult:
    """Result of matching one edited image against a raw image set."""

    edited_path: Path
    edited_hash: int
    matched_raw_path: Optional[Path]
    matched_raw_hash: Optional[int]
    distance: Optional[int]  # None if no match
    status: str  # "matched" | "no_match" | "unreadable"



def find_best_match(
    edited: ImageHash,
    raw_hashes: Sequence[ImageHash],
    max_distance: int,
) -> MatchResult:
    """Find the closest raw match for a given edited image hash.

    Parameters
    ----------
    edited:
        The edited image hash.
    raw_hashes:
        Sequence of raw image hashes.
    max_distance:
        Maximum Hamming distance allowed. If best distance is larger,
        a "no_match" status is returned.

    Returns
    -------
    MatchResult
        The best match information.
    """

    best_idx = None
    best_dist = 10**9

    # Tight loop: avoid extra attribute lookups
    ehash = edited.dhash
    for i, rh in enumerate(raw_hashes):
        d = hamming_distance(ehash, rh.dhash)
        if d < best_dist:
            best_dist = d
            best_idx = i
            if d == 0:
                break  # perfect match; can't do better

    if best_idx is None:
        return MatchResult(
            edited_path=edited.path,
            edited_hash=edited.dhash,
            matched_raw_path=None,
            matched_raw_hash=None,
            distance=None,
            status="no_match",
        )

    best = raw_hashes[best_idx]
    if best_dist <= max_distance:
        return MatchResult(
            edited_path=edited.path,
            edited_hash=edited.dhash,
            matched_raw_path=best.path,
            matched_raw_hash=best.dhash,
            distance=best_dist,
            status="matched",
        )

    return MatchResult(
        edited_path=edited.path,
        edited_hash=edited.dhash,
        matched_raw_path=best.path,
        matched_raw_hash=best.dhash,
        distance=best_dist,
        status="no_match",
    )
