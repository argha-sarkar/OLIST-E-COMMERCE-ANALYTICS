"""Download the Olist dataset from Kaggle into data/raw.

Needs a free Kaggle account and an API token:
  1. kaggle.com -> your profile -> Settings -> "Create New Token"
  2. save kaggle.json to ~/.kaggle/kaggle.json   (Windows: C:\\Users\\<you>\\.kaggle\\kaggle.json)
  3. python src/load/download_data.py

The data is NOT committed to git: CC BY-NC-SA licence, and ~120 MB of CSV.
"""
from __future__ import annotations

import sys
import zipfile

from src import config
from src.utils import LOG

DATASET = "olistbr/brazilian-ecommerce"


def main() -> int:
    config.ensure_dirs()
    existing = [f for f in config.RAW_FILES.values() if (config.RAW_DIR / f).exists()]
    if len(existing) == len(config.RAW_FILES):
        LOG.info("all 9 files already present in %s -- nothing to do", config.RAW_DIR)
        return 0

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        LOG.error("kaggle package missing. Run: pip install -r requirements.txt")
        return 1

    try:
        api = KaggleApi()
        api.authenticate()
    except Exception as exc:
        LOG.error(
            "Kaggle authentication failed (%s).\n"
            "Create an API token at kaggle.com -> Settings -> Create New Token,\n"
            "save it to ~/.kaggle/kaggle.json, then run this script again.\n"
            "Or download the zip manually and unzip it into %s",
            exc, config.RAW_DIR,
        )
        return 1

    LOG.info("downloading %s ...", DATASET)
    api.dataset_download_files(DATASET, path=str(config.RAW_DIR), unzip=False)

    zips = sorted(config.RAW_DIR.glob("*.zip"))
    for z in zips:
        LOG.info("unzipping %s", z.name)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(config.RAW_DIR)
        z.unlink()

    found = [f for f in config.RAW_FILES.values() if (config.RAW_DIR / f).exists()]
    LOG.info("%d/%d files ready in %s", len(found), len(config.RAW_FILES), config.RAW_DIR)
    if len(found) < len(config.RAW_FILES):
        LOG.error("some files are missing -- check the folder")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
