# Contributing to Sarvam AI assistant for NVDA

Thank you for your interest in improving this add-on. Accessibility is the
priority: every change must keep the interface fully usable with a screen
reader and the keyboard.

## Development setup

1. Install [NVDA](https://www.nvaccess.org/) and Python 3.8+ (only needed to run
   the build script; NVDA ships its own Python for the add-on runtime).
2. Clone this repository.
3. Build and install the add-on:
   ```bash
   python build.py
   ```
   Then install the generated `.nvda-addon` from NVDA's Add-on Store
   (*Install from external file*). Restart NVDA.

For a fast edit loop you can also enable NVDA's *scratchpad* development mode and
symlink `addon/globalPlugins/sarvamAI` into the scratchpad's `globalPlugins`
folder, then reload plugins with `NVDA+Ctrl+F3`.

## Project layout

```
addon/globalPlugins/sarvamAI/
  __init__.py     GlobalPlugin: menu, gestures, wiring
  client.py       All Sarvam HTTP calls (single source of truth)
  constants.py    Endpoints, models, voices, languages
  config.py       NVDA config spec + API key obfuscation
  errors.py       Typed exceptions + HTTP error mapping
  tasks.py        Background threads + accessible progress dialog
  audioutils.py   WAV playback / save
  recorder.py     Microphone capture via Windows MCI
  imaging.py      Image -> PDF conversion (GDI+) for OCR
  ocr.py          Windows OCR engine integration + screen capture
  updatecheck.py  Optional GitHub release check
  logger.py       Logging to NVDA log + rotating file
  ui/             wx dialogs and the settings panel
```

## Coding guidelines

- **No third-party runtime dependencies.** NVDA bundles a limited Python; use
  the standard library (`urllib`, `ctypes`, `wave`, `zipfile`, …).
- Keep all networking inside `client.py`; UI code should never call `urllib`.
- Never block NVDA's main thread. Long operations run through
  `tasks.run_task(...)`.
- Every user-visible string must be wrapped in `_()` and preceded by a
  `# Translators:` comment where helpful. Regenerate the template with
  `python build.py --pot`.
- Match the existing tab-indented style (NVDA convention).
- Label every control; verify focus order and that status is announced.

## Testing

- `python -m py_compile` on changed files (CI does this for all files).
- Manually exercise the changed dialog with NVDA running and speech on.
- Confirm error paths (no key, wrong key, offline, no credits) speak a clear
  message rather than failing silently.

## Commit messages & pull requests

- Write focused commits with descriptive messages.
- Describe the accessibility impact of your change in the PR.
- Update `CHANGELOG.md` under an *Unreleased* heading.

By contributing you agree that your contributions are licensed under the
GNU General Public License version 2.
