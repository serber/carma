# Plate OCR via fast-plate-ocr, plus KZ/RU format validation.
#
# RU plates use only the 12 GOST letters that are visual homoglyphs of
# latin (А В Е К М Н О Р С Т У Х -> A B E K M H O P C T Y X). The OCR
# model's alphabet is plain "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" -- it
# has no Cyrillic classes at all -- so it already reads these glyphs as
# their latin twin at inference time; no special-casing needed there. The
# CYRILLIC_TO_LATIN map below is for normalizing plate strings that arrive
# from elsewhere (e.g. a watchlist entry someone typed with Cyrillic
# letters), so they compare equal to OCR output.
#
# The OCR model's own "region" head (see its plate config) is a *country*
# classifier trained on a different taxonomy (~65 countries, notably not
# including Kazakhstan or Russia) -- unrelated to the KZ/RU plate-format
# tagging required here, which is done with our own regex sanity-check.
from __future__ import annotations

import logging
import re

import cv2
import numpy as np
from fast_plate_ocr import LicensePlateRecognizer

logger = logging.getLogger(__name__)

CYRILLIC_TO_LATIN = {
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
}

# KZ: 3 digits + 3 letters + 2-digit region, e.g. "123ABC02".
_KZ_RE = re.compile(r"^\d{3}[A-Z]{3}\d{2}$")
# RU: 1 letter + 3 digits + 2 letters + 2-3 digit region, e.g. "A123BC77".
_RU_RE = re.compile(r"^[A-Z]\d{3}[A-Z]{2}\d{2,3}$")


def normalize_plate(text: str) -> str:
    """Uppercases and maps Cyrillic GOST-homoglyph letters to latin."""
    text = text.upper().replace(" ", "")
    return "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in text)


def classify_plate(text: str) -> str:
    """Returns "KZ", "RU", or "unknown" based on the plate string shape."""
    if _KZ_RE.match(text):
        return "KZ"
    if _RU_RE.match(text):
        return "RU"
    return "unknown"


class PlateReader:
    def __init__(self, model_name: str) -> None:
        self._recognizer = LicensePlateRecognizer(hub_ocr_model=model_name)
        logger.info("OCR model loaded model=%s", model_name)

    def read(self, crop: np.ndarray) -> tuple[str, float, str] | None:
        """Runs OCR on a cropped plate image (BGR). Returns
        (plate_string, confidence, format) or None if the crop is empty."""
        if crop.size == 0:
            return None

        color_mode = self._recognizer.config.image_color_mode
        if color_mode == "grayscale":
            crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        elif color_mode == "rgb":
            crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

        prediction = self._recognizer.run_one(crop, return_confidence=True)
        plate = prediction.plate
        confidence = _mean_confidence(prediction.char_probs, len(plate))
        return plate, confidence, classify_plate(plate)


def _mean_confidence(char_probs: np.ndarray | None, plate_length: int) -> float:
    if char_probs is None or plate_length == 0:
        return 0.0
    # char_probs covers every model slot (including trailing padding);
    # only the leading plate_length slots correspond to real characters.
    return float(np.mean(char_probs[:plate_length]))
