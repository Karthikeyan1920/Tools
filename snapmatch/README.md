# SnapMatch

SnapMatch is a cross-platform command-line tool that finds the **closest matching raw/original photo** for each **edited** photo using a perceptual **dHash**, then copies the matched originals into an output folder.

It’s designed for workflows where filenames change during editing/export, but the *visual content* is still the same.

## What it does

You provide:

- **Path 1**: raw/original images folder  
- **Path 2**: edited images folder  
- **Path 3**: output folder (can be empty or non-empty)

SnapMatch will:

1. Recursively scan raw images and compute a 64-bit dHash for each.
2. Recursively scan edited images and compute a dHash for each.
3. For each edited image, find the raw image with the smallest Hamming distance.
4. Copy/link the matched raw image into the output folder.
5. Write a `mapping.csv` report into the output folder.

## Quick start (end users)

If you publish a GitHub Release with binaries:

- Download the correct binary for your OS
- Run:

```bash
snapmatch --raw "/path/to/raw" --edited "/path/to/edited" --out "/path/to/output"
```

## Install (for developers)

```bash
pip install -e .
```

## Usage

```bash
snapmatch --raw "/path/to/raw" --edited "/path/to/edited" --out "/path/to/output"
```

Common options:

```bash
snapmatch --raw RAW --edited EDITED --out OUT \
  --max-distance 3 \
  --workers 0 \
  --report-xlsx
```

- `--max-distance`: maximum Hamming distance allowed (default: 3). Above this, the file is marked as `no_match`.
- `--workers`: number of processes for hashing raw images. `0` means “auto” (default). Use `1` to disable multiprocessing.
- `--report-xlsx`: also write `mapping.xlsx` (requires optional dependency `openpyxl`).
- `--mode`: `copy` (default), `hardlink`, or `symlink`.
- `--preserve-raw-subdirs`: preserve raw folder subdirectories inside the output.
- `--dry-run`: don’t copy anything—only create the report.

## Output

In your output folder you’ll get:

- Matched raw images copied/linked from Path 1
- `mapping.csv` — the audit trail
- optionally `mapping.xlsx`
- optionally `snapmatch_cache.csv` — raw hash cache for faster re-runs

## Build standalone binaries (no Python required for end users)

### PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --name snapmatch -m snapmatch.cli
```

The binary will be in `dist/`.

> macOS note: unsigned binaries may be blocked by Gatekeeper. Users can right-click → Open the first time.

## GitHub Releases

Recommended flow:

- Keep **source code** in the repo
- Use GitHub Actions to build Windows + macOS binaries
- Attach binaries to **GitHub Releases** (do not commit binaries to git)

See `.github/workflows/build.yml`.

## Where this can be used

- **Relinking exports to camera originals** when editing tools rename files.
- **Photo dedup / near-duplicate detection** (find visually similar images).
- **Forensics / QA**: verify that a processed image corresponds to the correct source.
- **Dataset cleanup**: map “augmented” images back to the original.
- **Content pipelines**: match thumbnails or resized images to their master assets.

## License

MIT
