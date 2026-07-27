# Frame differencing so inference doesn't run on every frame.
#
# TODO(stage 2): threshold + ROI from config, return whether motion was
# detected (feeds the "motion events" counter).

import numpy as np


def detect_motion(prev_frame: np.ndarray, frame: np.ndarray, threshold: int, roi: tuple[int, int, int, int] | None) -> bool:
    raise NotImplementedError
