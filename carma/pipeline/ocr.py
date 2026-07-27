# Plate OCR via fast-plate-ocr (or equivalent ONNX OCR), plus KZ/RU format
# validation. RU plates use only the 12 GOST letters that are visual
# homoglyphs of latin (А В Е К М Н О Р С Т У Х -> A B E K M H O P C T Y X),
# so RU reads are mapped to latin rather than requiring full Cyrillic OCR.
#
# TODO(stage 3, atomic steps 17-19): run OCR on the cropped plate image,
# apply the homoglyph map, sanity-check against KZ/RU formats, return the
# matched string + confidence + format tag (KZ / RU / unknown). Feeds the
# "OCR reads" counter.

import numpy as np

CYRILLIC_TO_LATIN = {
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X",
}


def read_plate(crop: np.ndarray) -> tuple[str, float, str]:
    """Returns (plate_string, confidence, format) where format is one of
    "KZ", "RU", "unknown"."""
    raise NotImplementedError
