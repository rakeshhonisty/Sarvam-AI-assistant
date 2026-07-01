# Architecture

## Overview

The add-on is an NVDA **global plugin**. It adds a *Sarvam AI* submenu to the
Tools menu, a settings category to NVDA's Settings dialog, and a set of unbound
input gestures. All feature UIs are standard `wx` dialogs built with NVDA's
`gui.guiHelper`, so they inherit NVDA's accessibility behaviour.

```
                +-------------------------------+
   NVDA menu -> |        GlobalPlugin           | <- input gestures
   Settings  -> |  (__init__.py, ui/settings)   |
                +---------------+---------------+
                                | opens
                     +----------v-----------+
                     |     ui/ dialogs      |   TTS, STT, Translate,
                     | (wx, guiHelper)      |   Chat, OCR, Logs, About
                     +----------+-----------+
                                | run_task(func)
                     +----------v-----------+
                     |   tasks.run_task     |   worker thread +
                     | (thread + progress)  |   accessible cancel dialog
                     +----------+-----------+
                                | calls
                     +----------v-----------+
                     |   client.SarvamClient|   urllib only; every endpoint
                     | (constants, errors)  |   and the wire format live here
                     +----------------------+
                                |
                        https://api.sarvam.ai
```

## Layers

- **Presentation** (`ui/`): dialogs and the settings panel. No networking here;
  they gather input, call `tasks.run_task`, and render results. Every control is
  labelled; results land in read-only multiline fields that a screen reader can
  review.
- **Orchestration** (`tasks.py`): moves blocking work to a daemon thread and
  marshals success/error back to the wx main thread via `wx.CallAfter`. Provides
  a custom, fully accessible progress dialog with a working Cancel that flips a
  cooperative `CancelToken`.
- **Service** (`client.py`): the only module that talks HTTP. Uses `urllib` with
  retry/backoff, timeout, optional proxy, multipart encoding, the batch job
  lifecycle for OCR, and maps every HTTP failure to a typed `SarvamError`.
- **Domain data** (`constants.py`): endpoints, model names, voices, languages —
  the single place to adjust if Sarvam changes something.
- **Support**: `config.py` (NVDA config spec + key obfuscation), `errors.py`
  (typed exceptions + friendly messages), `logger.py`, `audioutils.py`,
  `recorder.py` (MCI mic capture), `imaging.py` (GDI+ image→PDF), `ocr.py`
  (Windows OCR + screen capture), `updatecheck.py`.

## Key design decisions

- **Zero third-party dependencies.** NVDA does not bundle `requests`, Pillow or
  PyAudio, so HTTP is `urllib`, imaging is GDI+ via `ctypes`, and microphone
  capture is the Windows MCI API via `ctypes`. The packaged add-on is therefore
  self-contained.
- **Never freeze NVDA.** All network and recognition work is off the main
  thread; the UI stays responsive and every long task can be cancelled.
- **Accessibility-first.** Only standard NVDA/wx controls are used — no custom
  drawn widgets. Status changes are spoken via `ui.message`.
- **OCR via PDF.** Sarvam OCR ingests PDFs; images and screen/clipboard captures
  are converted to a one-page PDF (`imaging.py`) so a single OCR code path
  serves every source. Windows OCR remains available for instant offline use.
- **Secrets.** The API key is stored obfuscated (XOR + base64) in NVDA config —
  documented as obfuscation, not encryption.

## Threading & cancellation

`run_task(func, on_success, on_error)` calls `func(cancel, progress)` on a
worker thread. `func` polls `cancel.check()` at safe points (and between OCR
poll iterations) and reports coarse progress. Results and errors are delivered
on the main thread, where dialogs and spoken messages are safe to touch.
