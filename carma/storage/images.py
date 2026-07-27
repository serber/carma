# Saves the full frame + cropped-plate image per hit to storage.images_dir.
#
# TODO(stage 3, atomic step 21): filename scheme (timestamp-based), JPEG
# encode/write, return paths for storage.db.insert_hit().

import numpy as np


def save_hit_images(frame: np.ndarray, crop: np.ndarray, images_dir: str) -> tuple[str, str]:
    """Returns (frame_path, crop_path)."""
    raise NotImplementedError
