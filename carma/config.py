# Loads and validates config.yaml (see config.example.yaml).
#
# TODO(stage 1, atomic step 2): dataclasses for camera / motion / detection /
# ocr / dedup / watchlist / dashboard / storage / log_level sections, a
# load_config(path) -> Config that reads YAML, fills defaults, and raises a
# clear error naming the offending key on invalid config (this feeds the
# startup self-check's "config OK" line).
