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

- [ ] 12. `pipeline/motion.py`: frame differencing + threshold + ROI.
- [ ] 13. Dashboard: "motion events" counter.
- [ ] 14. Pick and vendor a pretrained plate-detector ONNX model.
- [ ] 15. `pipeline/detect.py`: inference via onnxruntime.
- [ ] 16. Dashboard: "detections" counter.

## Stage 3 — OCR + storage

- [ ] 17. Integrate fast-plate-ocr.
- [ ] 18. RU Cyrillic homoglyph -> latin mapping (map already stubbed in
      `pipeline/ocr.py`).
- [ ] 19. KZ / RU format validation (sanity-check) + format tag
      (KZ / RU / unknown).
- [ ] 20. `storage/db.py`: SQLite schema (timestamp, plate, confidence,
      format) + writer.
- [ ] 21. `storage/images.py`: save full frame + cropped-plate image per
      hit.
- [ ] 22. Dashboard: browsable recent-hits list with images.
- [ ] 23. Dashboard: "OCR reads" counter.

## Stage 4 — Dedup, watchlist, polish

- [ ] 24. `pipeline/dedup.py`: per-plate time-window dedup.
- [ ] 25. Watchlist: config + highlight matching hits on the dashboard.
- [ ] 26. Dashboard: CPU temperature, FPS, log tail.
- [ ] 27. Polish: error handling at pipeline boundaries, edge cases.

## Open questions

- Camera type (CSI vs USB) — resolved: **CSI**, default backend
  `picamera2`. `OpenCVSource` (USB) kept as the config-swappable
  alternative per spec.
