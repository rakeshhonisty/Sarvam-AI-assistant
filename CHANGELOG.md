# Changelog

All notable changes to the Sarvam AI assistant NVDA add-on are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.5] - 2026-08-07

Fixes text to speech, which could not produce audio with the current Sarvam
model. All findings below were verified live against the Sarvam API.

### Bug fixes
- **Text to speech now works with bulbul:v3.** The add-on was sending `pitch`
  and `loudness` with every request, but Sarvam's bulbul:v3 model rejects those
  two parameters outright ("Pitch and loudness parameters are currently not
  supported for the Bulbul V3 model"). Every v3 request therefore failed with
  HTTP 400. They are no longer sent.
- **The sliders now work.** Because the request above always failed, changing
  any slider appeared to do nothing. The dialog now offers **Speech speed**
  (0.5x - 2.0x) and **Expression** (5% - 100%), which are the two controls
  bulbul:v3 actually supports, and both are applied and clamped to the API's
  real ranges.
- **The voice list was wrong.** Several bulbul:v2-only voices (anushka,
  manisha, vidya, arya, abhilash, karun, hitesh) were being offered for
  bulbul:v3, which the API rejects as incompatible. The catalogue is now the
  verified bulbul:v3 voice set.

### Improvements
- **All 37 Sarvam bulbul:v3 voices are now included** - 14 female and 23 male -
  each one verified live against the API. They are still filtered by speaking
  style and gender so the list stays short and relevant.
- **bulbul:v2 has been removed completely**, as Sarvam is deprecating it. The
  add-on now targets bulbul:v3 only, and settings were simplified accordingly.
- Speech speed and Expression are also configurable in Advanced settings, with
  the correct bulbul:v3 ranges.

### Verified
Tested end to end with a Kannada Word document: upload -> automatic language
detection (kn-IN) -> News reader / Female voice filtering -> Convert -> MP3
export.

## [1.0.4] - 2026-07-30

A large usability and quality release driven by user testing, focused on making
every module behave consistently and on getting far better OCR results.

### Bug fixes
- **Save buttons appeared before there was anything to save.** Every module now
  follows one rule: perform the task, show the result, and only then reveal the
  save options. In Text to Speech, **Save as MP3 now appears after Convert**,
  which is where it makes sense.
- **Sliders did not say what they were.** Speed, Pitch and Volume now announce
  their purpose and value (for example "Speech speed percent, 100") instead of
  an anonymous "slider".
- **The voice list showed voices that did not match the chosen style or
  gender.** Voices are now filtered live: pick a style (for example News
  reader) and a gender, and only the matching voices are listed.
- **Duplicate operation entries in Translation.** Translate, Transliterate and
  Detect language are now chosen from a single Operation dropdown inside one
  dialog.
- **Two OCR engines produced conflicting results.** The offline Windows OCR
  engine has been removed; Sarvam Cloud OCR is now the single engine.
- Large transcripts, OCR output and AI responses no longer make the result
  boxes sluggish.

### Improvements
- **OCR is now Sarvam Document Intelligence.** Layout analysis is used so
  **headings, lists, tables, multi-column text and reading order are
  preserved** instead of being flattened into plain text. Multi-page PDFs keep
  their correct page order.
- **New: Save as Markdown (.md)** in OCR and AI Workforce, so you keep Sarvam's
  original structured output and can convert it to any format you like.
  **Save as Word (.docx) now creates real Word headings and tables.**
- **Large audio just works.** Files beyond the real-time limit are automatically
  sent through Sarvam's batch transcription API and merged into one complete
  transcript - no manual splitting.
- **AI Assistant, AI Summary and AI Workforce are now one module: AI
  Workforce**, with Task modes (AI Assistant, AI Summary, Document Analysis,
  General AI Workforce, Content Generation, Question Answering, File Analysis).
  Tab order is deliberate: Ask a question is focused, Shift+Tab reaches Upload
  file, Tab moves to the Response, then to Task mode and the rest.
- **Upload a file almost anywhere.** Text to Speech accepts TXT/DOCX/EPUB;
  Translation accepts those plus PDF and images (read with OCR first); AI
  Workforce additionally accepts audio (transcribed automatically).
- **Auto detect language** for OCR, and long text is translated in chunks and
  rejoined so there is no length limit.
- **New: Generate API key button** in Settings, which opens the official Sarvam
  developer portal in your browser.
- **New: Batch processing speed (1x - 10x)** in Advanced settings, controlling
  how many pieces of work are processed at once.
- "From selection" and "From clipboard" buttons were removed from Translation
  and AI Workforce in favour of the upload workflow.

### Notes
- Advanced settings is retained and now contains the batch processing setting.
- Every save action opens the standard Windows Save As dialog, preserves
  Unicode and prompts before overwriting.

## [1.0.3] - 2026-07-10

### Added
- **AI Workforce (Sarvam-105B)** – a reasoning / agentic layer using the
  `sarvam-105b` model (128K context): choose a worker role (assistant,
  researcher, writer, programmer, planner, analyst, tutor, or multi-step task
  agent), a reasoning effort (low/medium/high) and optional wiki grounding, then
  run a task. Results save to .txt or .docx.
- Hero banner and an expanded "Who this is for" section emphasising how the
  add-on helps the blind and visually-impaired community.

### Fixed
- **You can now always exit a window.** Pressing Escape anywhere in any
  dialog (including inside text boxes) closes it and returns focus. Every dialog
  destroys cleanly on close, and the API-key setup dialog now has both a
  **Close** and a **Cancel** button. This resolves getting "stuck" in the
  settings / API-key windows.

### Notes
- Default language remains Auto-detect (handles code-mixed text).
- `lastTestedNVDAVersion` stays at 2026.1 (current stable) for the store's
  stable channel.

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
