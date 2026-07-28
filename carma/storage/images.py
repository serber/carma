# Saves the full frame + cropped-plate image per hit to storage.images_dir.
# Returns filenames (not full paths) -- HitStore stores those, and the
# dashboard serves storage.images_dir directly as static files, so a
# filename is all either side needs.
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np


def save_hit_images(frame: np.ndarray, crop: np.ndarray, images_dir: str) -> tuple[str, str]:
    """Returns (frame_filename, crop_filename)."""
    directory = Path(images_dir)
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    unique = uuid.uuid4().hex[:6]
    frame_filename = f"{stamp}_{unique}_frame.jpg"
    crop_filename = f"{stamp}_{unique}_crop.jpg"

    cv2.imwrite(str(directory / frame_filename), frame)
    cv2.imwrite(str(directory / crop_filename), crop)
    return frame_filename, crop_filename


def clear_images(images_dir: str) -> None:
    """Deletes every file directly in images_dir. Called alongside
    HitStore.clear() by the dashboard's "clear all" action."""
    directory = Path(images_dir)
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        if entry.is_file():
            entry.unlink()


def images_dir_size(images_dir: str) -> int:
    """Total bytes used by files directly in images_dir -- matches exactly
    what clear_images() would free, not the whole filesystem's usage."""
    directory = Path(images_dir)
    if not directory.is_dir():
        return 0
    return sum(entry.stat().st_size for entry in directory.iterdir() if entry.is_file())
