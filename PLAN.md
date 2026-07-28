# carma — build plan

Atomic, checkable steps derived from the build order in [SPEC.md](SPEC.md).
Check items off as they land; resume at the first unchecked box.

## Stage 1 — Skeleton
Goal: mount, power on, see the live frame and confirm it's alive.

- [x] 1. Project scaffold: directory layout, `pyproject.toml`, stub modules
      with `NotImplementedError` + TODO markers, `config.example.yaml`,
      `systemd/carma.service`, README bring-up checklist stub.
- [x] 2. `config.py`: load/validate `config.yaml` (camera, motion, detection,
      ocr, dedup, watchlist, dashboard, storage, log_level), clear error on
      bad config. Tests in `tests/test_config.py`.
- [x] 3. Logging: structured, to journald, level from config.
      `carma/logging_setup.py` + wired into `service.run()` (config load ->
      logging setup -> "config OK" log line). Verified end-to-end with
      `python -m carma --config config.example.yaml`.
- [x] 4. `capture/base.py` abstract interface — `FrameSource` ABC plus a
      shared `FrameRateTracker` helper used by both backends.
- [x] 5. `Picamera2Source`: real implementation (CSI — default backend, this
      device has a ribbon-cable camera). picamera2 import deferred to
      `start()` so the module loads fine off-Pi too.
- [x] 6. `OpenCVSource`: real implementation (USB — also useful for
      developing/testing off-Pi with a laptop webcam). Tested with a mocked
      `cv2.VideoCapture` in `tests/test_opencv_source.py`.
- [x] 7. Startup self-check: `carma/selfcheck.py` — camera OK / FAILED
      logged clearly; a camera that fails to open does **not** crash the
      service, so the dashboard stays reachable for diagnosis (matches the
      spec's "dead camera -> 0 frames" behavior). config OK already covered
      by step 2/3.
- [x] 8. `web/app.py`: FastAPI app + `/stream.mjpg` MJPEG endpoint reading
      from a background `CaptureLoop` (`carma/capture_loop.py`); falls back
      to a red "camera unavailable" placeholder frame when the source has
      no live capture loop.
- [x] 9. Dashboard: `/api/status` JSON with `frames_captured` +
      `motion_events`/`detections`/`ocr_reads` (0 until stage 2/3 wire them)
      + fps + self-check, polled by the `/` page every second.
- [x] 10. `scripts/install.sh`: real install logic (venv w/
       `--system-site-packages` for picamera2, pip install, seed
       config.yaml, install + enable the systemd unit). Not runnable off-Pi
       (apt-based); will get its first real run at physical bring-up.
- [x] 11. README: bring-up checklist updated + a "Development (off-Pi)"
       section for iterating with `uv` before deploying.

Verified end-to-end off-Pi: ran `python -m carma` with `camera.backend:
opencv` pointed at a nonexistent device — self-check logs `camera FAILED`,
service keeps running, `/` and `/api/status` respond normally,
`frames_captured` stays 0, `/stream.mjpg` serves the placeholder JPEG.
Real CSI hardware behavior (`Picamera2Source`) still needs a run on the
actual Pi — first item to confirm at physical bring-up.

## Stage 2 — Motion + detection

- [x] 12. `pipeline/motion.py`: `MotionDetector` — stateful frame
      differencing (Gaussian-blurred grayscale diff) with `threshold` +
      `min_area` + optional ROI. Tested in `tests/test_motion.py`.
- [x] 13. Dashboard: "motion events" counter — wired via `CaptureLoop`.
- [x] 14. Plate-detector model: **open-image-models** (`create_detector`),
      default `yolo-v9-t-384-license-plate-end2end` — the same
      detector/confidence pairing `fast-alpr` uses by default with
      `fast-plate-ocr` (same author, models built to work together; see
      SPEC.md's OCR pick). Registered models auto-download + cache; no raw
      `.onnx` vendored into the repo.
- [x] 15. `pipeline/detect.py`: `PlateDetector` wraps `create_detector`,
      returns `(x1, y1, x2, y2, confidence)` boxes. `carma/selfcheck.py`
      gained `check_model()` (mirrors `check_camera()`: logs "model OK" /
      "model FAILED" and returns `None` on failure rather than crashing).
      `scripts/fetch_models.py` pre-downloads the configured model at
      install time (`HOME=$INSTALL_DIR` so the cache lands where the
      systemd-run service will actually look for it) so normal offline
      operation never needs network access, per SPEC's offline-first
      requirement. Verified against a real image (car photo, no plate
      present) end-to-end: model downloads, caches, loads, and runs
      inference without error.
- [x] 16. Dashboard: "detections" counter — wired via `CaptureLoop`;
      detected boxes are also drawn on the MJPEG preview (green
      rectangles), doubling as a live "is detection working" check while
      aiming the camera.

Verified end-to-end off-Pi (same nonexistent-camera-device pattern as
stage 1, this time with the model also loaded): self-check logs `model OK`
+ `camera FAILED`, `/api/status` reports `self_check: {config: true,
camera: false, model: true}`, motion/detections counters correctly stay 0
since there's no live capture loop without a camera. 46 tests passing.

## Stage 3 — OCR + storage

- [x] 17. Integrated **fast-plate-ocr** (`LicensePlateRecognizer`), default
      model `cct-xs-v2-global-model` — matches what `fast-alpr` pairs with
      our detector by default. Its alphabet is plain `0-9A-Z` (no Cyrillic
      classes at all); the model's own "region" head is a ~65-country
      classifier that doesn't include KZ/RU, confirmed by inspecting its
      plate config, so it's unused here in favor of our own regex tagging.
- [x] 18. RU Cyrillic homoglyph -> latin mapping: kept in
      `pipeline/ocr.py` as `normalize_plate()`, but it turns out to not be
      needed on OCR *output* -- since the model's alphabet has no
      Cyrillic classes, glyphs that are visual homoglyphs (А/A, В/B, ...)
      already decode as their latin twin at inference time. The map is
      used instead to normalize plate strings from elsewhere (e.g. a
      watchlist entry typed with Cyrillic letters) for comparison.
- [x] 19. `classify_plate()`: regex sanity-check tagging KZ
      (`\d{3}[A-Z]{3}\d{2}`) / RU (`[A-Z]\d{3}[A-Z]{2}\d{2,3}`) / unknown.
- [x] 20. `storage/db.py`: `HitStore` — SQLite schema (timestamp, plate,
      confidence, format, frame/crop filenames), lock-guarded single
      connection (one writer thread, dashboard readers).
- [x] 21. `storage/images.py`: `save_hit_images()` — timestamp + uuid
      filenames, returns filenames only (not full paths); dashboard serves
      `storage.images_dir` directly via `StaticFiles`.
- [x] 22. Dashboard: `/hits` page — table of recent hits with clickable
      crop thumbnails (full frame behind the link), linked from `/`.
- [x] 23. Dashboard: "OCR reads" counter — wired via `CaptureLoop`.

`carma/selfcheck.py` gained `check_ocr()` / `check_storage()` (same
non-fatal pattern as camera/model). `scripts/fetch_models.py` now
pre-downloads both the detector and OCR models. Every OCR read is stored
regardless of confidence or format tag (including "unknown") -- no
dedup/filtering yet, that's stage 4 by design; the operator can judge
low-confidence/unknown reads visually via the crop thumbnail.

Verified with real inference (not just mocks): downloaded the OCR model,
ran it against fast-plate-ocr's own sample plate crops (`AD799KB`,
`KRW301`, both confidence 1.0, correctly tagged "unknown" since they're
not KZ/RU shaped). End-to-end smoke test (camera intentionally
unavailable): self-check logs `model/ocr/storage OK`, manually inserted a
hit and confirmed `/hits` renders it with a working `/images/...` link.
76 tests passing.

## Stage 4 — Dedup, watchlist, polish

- [ ] 24. `pipeline/dedup.py`: per-plate time-window dedup.
- [ ] 25. Watchlist: config + highlight matching hits on the dashboard.
- [ ] 26. Dashboard: CPU temperature, FPS, log tail.
- [ ] 27. Polish: error handling at pipeline boundaries, edge cases.

## Open questions

- Camera type (CSI vs USB) — resolved: **CSI**, default backend
  `picamera2`. `OpenCVSource` (USB) kept as the config-swappable
  alternative per spec.
