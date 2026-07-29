# carma — build spec

> **Repo description:** Raspberry Pi ANPR box: spots and reads passing plates, live Wi-Fi dashboard.

## Your task

Scaffold and build this repository from scratch in **Python**, as a single
long-running service for a **Raspberry Pi 4**. Start with a runnable skeleton
(capture + motion + dashboard) so the camera can be aimed and confirmed alive,
then add detection, OCR, and local storage. Ask clarifying questions only where
this spec is genuinely silent — most decisions are already made below.

## What it is

A headless appliance that sits **inside a parked car at the curb**, watches
passing traffic through a camera, detects and reads license plates
(**Kazakhstan _and_ Russia formats**), and stores every read locally with
cropped images and timestamps. Kazakhstan is the actual target; Russia is
included so the device can be tested on locally abundant traffic.

Plate formats to support:
- **KZ** — e.g. `123 ABC 02`: digits + latin letters + region code.
- **RU** — e.g. `А123ВС 77`: letter + 3 digits + 2 letters + region. Russian
  plates use only the 12 GOST letters that are visual homoglyphs of latin
  (А В Е К М Н О Р С Т У Х → A B E K M H O P C T Y X), so map them to their
  latin equivalents — **no full Cyrillic OCR needed**; the character set is
  effectively the same latin/digit set for both countries.

It runs **fully offline — no internet**. The operator walks up to the car,
joins the Pi's own Wi-Fi, and reviews captures on a local web dashboard. The
purpose is to collect a browsable log of passing plates so a specific vehicle
(known by sight — make/colour) can be matched to its plate number.

## Decisions already made (do not re-litigate)

- **Target hardware:** Raspberry Pi 4, single camera.
- **OS:** Raspberry Pi OS Lite, **64-bit, Trixie (Debian 13)**.
- **Language/runtime:** Python, one `systemd` service.
- **Offline-first:** no hard internet dependency anywhere in the core path.
  Notifications = store locally + show in dashboard, **not** push.
- **Camera source is abstracted** (see Open questions): support both **CSI**
  (via `picamera2`) and **USB** (via OpenCV / V4L2) behind one interface,
  selectable in config.
- **Scenario:** daytime first. IR / night is a **future** add-on — leave a
  clean seam for it, don't build it now.
- **Observability is a first-class requirement**, not an afterthought (below).

## Pipeline

1. **Capture** — abstract source interface; concrete `picamera2` and `opencv`
   backends chosen by config. Expose raw frames + FPS.
2. **Motion trigger** — frame differencing, so inference does **not** run on
   every frame. Configurable threshold + ROI.
3. **Plate detection** — YOLO-style plate detector via `onnxruntime`
   (recommend an existing pretrained plate-detection model; detection is
   plate-agnostic so a generic model is fine).
4. **OCR** — recommend `fast-plate-ocr` (or equivalent ONNX OCR). Validate /
   tune for **both KZ and RU** plate formats; map RU Cyrillic homoglyphs to
   latin (see above). Per-format sanity-check + confidence score; tag each read
   with the format it matched (KZ / RU / unknown). OCR quality on both must be
   verifiable, not assumed.
5. **Dedup** — don't record the same plate repeatedly within a configurable
   time window.
6. **Store** — SQLite for records (timestamp, plate string, confidence) +
   saved full frame and cropped-plate image per hit. Optional **watchlist**:
   flag/highlight plates matching a user-supplied full or partial string.

## Observability (explicit requirement — no black box)

The operator's stated fear is "I turned it on and nothing happens, and I can't
tell why." Design against that from day one:

- **Per-stage counters** surfaced on the dashboard: frames captured, motion
  events, detections, successful OCR reads. Where the pipeline goes silent tells
  you which stage is stuck (dead camera → 0 frames; threshold too high → frames
  but 0 motion; bad angle/focus → motion but 0 detections; unreadable → 0 OCR).
- **Verbose structured logging** to journald at every stage, viewable with
  `journalctl -u carma-app -f`.
- **Startup self-check**, logged clearly: camera OK / model loaded OK / config
  OK — so init failures are visible, not silent.
- **`systemctl status`** must cleanly reflect running vs crashed.
- *(Optional, nice-to-have)* physical heartbeat: onboard LED blink or a small
  I2C OLED showing `frames / detections`, so "is it alive?" is answerable
  without a phone.

## Access model (local only, no internet)

- Pi runs as a **Wi-Fi access point**, broadcasting its own network;
  reachable at a fixed IP (e.g. `192.168.4.1`). Implemented via
  **NetworkManager** (`nmcli`, built into Raspberry Pi OS Trixie) rather
  than separate `hostapd`/`dnsmasq` services — same outcome (fixed-IP AP,
  local DHCP), fewer moving parts on an unattended device. See README's
  "Wi-Fi access point" section.
- **SSH** for logs / shell.
- **Local web dashboard** (FastAPI + uvicorn) at `http://192.168.4.1:8000`:
  - live **MJPEG preview** from the camera (doubles as the aiming tool at mount
    time),
  - CPU temperature, FPS, the per-stage counters,
  - browsable list of recent hits with cropped plate images,
  - tail of the log on the page.

AP setup is OS-level — put it in the README bring-up checklist rather than
code, but the dashboard + AP must be the first thing that works so the
device is inspectable immediately.

## Config

Single config file (YAML or env). At minimum: camera source type + params,
motion threshold + ROI, detection confidence threshold, dedup window, optional
watchlist, dashboard port, storage paths, log level.

## Suggested repo layout

```
carma/
  capture/        # abstract source + picamera2 / opencv backends
  pipeline/       # motion, detect, ocr, dedup
  storage/        # sqlite + image files
  web/            # FastAPI dashboard + MJPEG stream
  config.py       # load/validate config
  service.py      # main loop wiring the pipeline
  __main__.py
config.example.yaml
systemd/carma-app.service
scripts/install.sh
scripts/bootstrap.sh   # one-command clone+install
README.md         # bring-up checklist: flash, wire camera, AP setup, run, aim
```

## Build order

1. Skeleton: config load, abstract capture, MJPEG dashboard + counters, systemd
   unit, verbose logging, startup self-check. **Goal: mount, power on, see the
   live frame and confirm it's alive.**
2. Motion trigger + detection, counters wired through.
3. OCR + KZ format validation + storage + hit review in the dashboard.
4. Dedup, watchlist highlight, polish.

## Open questions

- **Camera type: CSI (ribbon) or USB?** Not decided. Build the abstraction
  either way; default the config to one and make switching a one-line change.
  If it materially affects a choice, ask.

## Non-goals (for now)

- No internet / cloud / push notifications in the core path.
- No IR / night capture yet (leave the seam).
- No owner lookup — the deliverable is the plate string.