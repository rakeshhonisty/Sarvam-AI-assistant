# Changelog

All notable changes to the Sarvam AI assistant NVDA add-on are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-07-01

Initial release.

### Added
- **Text to Speech** using Sarvam `bulbul` models: synthesise from the current
  selection, clipboard, typed text or a text file; play, pause, resume, stop and
  save WAV audio; voice, language and prosody controls; automatic chunking of
  long text.
- **Speech to Text** using Sarvam `saarika` models: transcribe an audio file or
  record the microphone (via the Windows MCI API, no external dependencies);
  optional translate-to-English mode using `saaras`; copy or save the transcript.
- **Translation** (`sarvam-translate` / `mayura`), **Transliteration** and
  **Language Detection** (`text-lid`) across English and 10 Indian languages.
- **AI Assistant** using Sarvam chat models (`sarvam-105b`, `sarvam-30b`): chat,
  summarise text and understand documents.
- **OCR**: primary **Sarvam Document OCR** (document-digitization service, 23
  languages, PDF/image input) plus an offline **Windows OCR** engine; recognised
  text can be translated or summarised with Sarvam.
- **Settings** panel integrated into NVDA's Settings dialog, with API key
  validation / connection test, per-feature defaults, folders, network options
  (timeout, retries, proxy), debug logging and restore-defaults.
- **NVDA menu** integration under Tools → Sarvam AI, plus unbound input gestures
  for every major action.
- Background threading with an accessible, cancellable progress dialog so NVDA
  never freezes.
- Logging with a viewer and export, dedicated rotating log file.
- Internationalisation scaffolding (gettext) with a generated `.pot` template.
- Documentation, GPL v2 license and a dependency-free build script producing a
  `.nvda-addon` package.

### Notes
- All Sarvam endpoints and schemas were verified against the live API and the
  published OpenAPI specification on 2026-07-01.
- Sarvam endpoints consume account credits; users supply their own funded API
  key.
