# carma — build plan

Atomic, checkable steps derived from the build order in [SPEC.md](SPEC.md).
Check items off as they land; resume at the first unchecked box.

## Stage 1 — Skeleton
Goal: mount, power on, see the live frame and confirm it's alive.

- [x] 1. Project scaffold: directory layout, `pyproject.toml`, stub modules
      with `NotImplementedError` + TODO markers, `config.example.yaml`,
      `systemd/carma.service`, README bring-up checklist stub.
- [ ] 2. `config.py`: load/validate `config.yaml` (camera, motion, detection,
      ocr, dedup, watchlist, dashboard, storage, log_level), clear error on
      bad config.
- [ ] 3. Logging: structured, to journald, level from config.
- [ ] 4. `capture/base.py` abstract interface — already defined, nothing
      left to do here.
- [ ] 5. `Picamera2Source`: real implementation (CSI — default backend, this
      device has a ribbon-cable camera).
- [ ] 6. `OpenCVSource`: real implementation (USB — also useful for
      developing/testing off-Pi with a laptop webcam).
- [ ] 7. Startup self-check: camera OK / config OK, logged clearly.
- [ ] 8. `web/app.py`: FastAPI app + MJPEG endpoint from the capture source.
- [ ] 9. Dashboard: "frames captured" counter.
- [ ] 10. `scripts/install.sh`: real install logic (venv w/
       `--system-site-packages` for picamera2, pip install, seed
       config.yaml, install + enable the systemd unit).
- [ ] 11. README: fill in the bring-up checklist as each piece above lands.

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
