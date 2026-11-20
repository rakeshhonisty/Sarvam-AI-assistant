# Changelog

All notable changes to the Sarvam AI assistant NVDA add-on are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [2.0] - 2026-11-20 - "sarvamAI-2.0"

A landmark release that brings the add-on up to date with Sarvam's latest
platform: new models, open models, model switching, an agent, AI vision,
Document AI, document translation, and upload / download in many formats.

### New models, and retired ones removed
- **Chat moves to Sarvam's Chat Completions V2** (`/v2/chat/completions`), which
  serves **Sarvam 105B** plus Sarvam's hosted **open models**: **GLM 5.3**,
  **GLM 5.3 Flash**, **Gemma 4 (31B)**, **DeepSeek V4.1 Flash** (and its
  Interactive variant), and - for keys with Provisioned Throughput -
  **DeepSeek V4 Pro**, **Kimi K3.1 Pro** and **Qwen 3.8 (27B)**.
- **Text to speech defaults to Bulbul v4 Flash** with its **222 persona
  voices**. Bulbul v3 (37 voices) stays for Malayalam and Odia, which v4 Flash
  does not cover - the add-on switches automatically and tells you.
- **Speech to text defaults to Saaras v4.**
- **Documents use Sarvam Document AI** (Sarvam Vision 2.1, `/doc-ai/v1`). The
  legacy document digitization API is used only as an automatic fallback.
- **Retired and removed:** `sarvam-m`, `sarvam-30b` and the other retired chat
  models, `bulbul:v2`, the `saarika` models, the legacy
  `/speech-to-text-translate` endpoint with `saaras:v2.5` (translation is now
  the `translate` output mode of Saaras), the undocumented `wiki_grounding`
  option, and the v2-only TTS `enable_preprocessing`, `pitch` and `loudness`
  parameters. Settings saved by 1.x are migrated automatically on first start.

### Model switching
- New **Model switching** window (menu, and an assignable gesture): choose the
  model for the AI Workforce and Agent, image/screen description, text to
  speech, speech to text, translation and documents. Each choice speaks a
  description: what the model is good at, context size, whether it sees images
  and its reasoning levels.
- **Check which models my key can use** asks Sarvam (`GET /v2/models`) and marks
  models your key cannot use.
- A **model switch inside AI Workforce**, with a reasoning list that adapts to
  each model (for example GLM accepts only Low/High; Gemma 4 thinks only when
  asked).
- New gesture: **switch to the next chat model and announce it**.

### Voice classification kept and extended (gender, purpose, language)
- The voice picker narrows down in steps: **Voice model -> Language -> Gender
  -> Purpose (nature of work) -> Voice**, on both Bulbul v4 Flash and v3.
- Purposes: Conversational; Narration, stories and audiobooks; News and
  documentary; Customer support, banking and business; Education and
  children; Ads, sales and social media; Devotional and spiritual; Drama,
  suspense and characters; Companion and assistant; Sports; Numbers and
  announcements; Formal; Expressive. Each purpose shows how many voices it has
  and sets matching speed and expression.
- v4 Flash personas are classified from their ids (`<name>_<lang>_<purpose>`),
  so new personas slot in automatically; genders are confirmed against
  Sarvam's recommended male/female tables. Voices read as, for example,
  "Ritu - Hindi - Banking (female)".

### Sarvam Agent (agentic features)
- New **Agent** task mode (also its own menu item): the model uses tools that
  run inside the add-on - read your attached files, translate, transliterate,
  detect language, **create speech files** with the right voice for a gender
  and purpose, and **save documents** in any format. One request like
  "translate this letter to Kannada, save it as Word and make an MP3 read by a
  female narration voice" is done end to end.
- Every step is announced and listed in **Agent steps**. The agent can only
  read the files you attach and only write new files into your output folder;
  it cannot overwrite, delete or run anything, and steps per task are capped.
- **Smart data extraction**: describe in plain words what you need from a
  document; the chat model writes the extraction schema and Document AI fills
  it - download as Excel, CSV or JSON.

### AI vision
- **Describe images**: attach photos or screenshots in AI Workforce; a vision
  model (Gemma 4 by default) describes them, reading all visible text.
- **Describe the screen**: new gestures describe the current window or the
  whole screen.

### Upload any file, download in the format you want
- Upload now reads **TXT, Markdown, Word, EPUB, HTML, RTF, PowerPoint, Excel,
  OpenDocument (text, spreadsheet, presentation), CSV, JSON, XML and
  subtitles**, plus **PDF, images and ZIPs of page images** (Document AI) and
  **audio** (transcribed) - in every dialog.
- Results now have a **Download format** list and a **Download** button:
  **Word, Markdown, web page (HTML), rich text (RTF), Excel, CSV, JSON, plain
  text** and, for timed transcripts, **SRT subtitles**. Markdown tables become
  real Word, HTML and Excel tables. The last format used is remembered.
- Audio downloads as **MP3, WAV, FLAC or AAC**; new sample rates up to 48 kHz.
- **Translate a whole document and keep its format**: PDF, Word, Excel,
  PowerPoint, HTML, Markdown or text in, the same format out, layout kept.
- AI Workforce accepts **several attachments at once** and keeps the
  **conversation** for follow-up questions (New conversation starts over).

### Speech to text
- Output modes: transcribe, translate to English, verbatim, romanised or
  code-mixed.
- **Key terms** (Saaras v4): names and jargon to spell correctly.
- **Separate speakers** (who said what) and **timings** for subtitles.
- Long audio goes to the batch API automatically (up to two hours); if the
  real-time API rejects a clip as too long it is retried as a batch job.
- More input formats: MP4, AIFF, AMR, WMA.

### Translation
- **Sarvam-Translate** offers all **22 scheduled Indian languages** (Assamese,
  Bodo, Dogri, Kashmiri, Konkani, Maithili, Manipuri, Nepali, Sanskrit,
  Santali, Sindhi, Urdu and more); Mayura keeps its styles.

### Under the hood
- New modules: `models.py` (catalogue), `agent.py`, `exporter.py`, `fileio.py`.
- 31 automated tests (`python -m unittest discover -s tests`) cover the voice
  catalogue, model rules, every export format, the file readers, the agent
  loop and the request shapes for Chat V2, Bulbul, batch STT, Document AI and
  document translation.

## [1.0.7] - 2026-08-11

Fixes a crash that stopped the settings panel opening, and makes Speech to Text
handle naturally mixed-language speech.

### Bug fixes
- **The Sarvam AI settings panel could not be opened** (reported by George on
  NVDA 2026.1.1): it failed with
  `UnboundLocalError: cannot access local variable 'sizer'`.
  Cause: the Speech speed and Expression controls were built with
  `wx.SpinCtrlDouble`, but NVDA's `guiHelper.associateElements()` only lays out
  a fixed set of control types (`wx.Button`, `wx.Choice`, `wx.ComboBox`,
  `wx.Slider`, `wx.SpinCtrl`, `wx.TextCtrl`). `wx.SpinCtrlDouble` is not in that
  set and is not a subclass of `wx.SpinCtrl`, so no layout branch ran and the
  helper's `sizer` variable was never assigned.
  Fix: those two settings now use `wx.SpinCtrl` and are edited as whole
  percentages. The range is preserved (speed 50-200%, expression 5-100%), the
  step is finer than before (1% instead of 0.05), and label association,
  keyboard navigation, speech and braille all behave normally. The exception is
  not caught or suppressed - the unsupported control is simply no longer used.
  Every other settings control was audited for the same problem; none remained.
- Settings saved by an older version that name a model Sarvam has since retired
  (the `saarika:*` speech-to-text models, or `bulbul:v2`) are now repaired
  automatically on start, instead of being sent to the API and failing.

### Speech to Text: mixed-language speech
- **Speaking Kannada and English in one sentence now transcribes as spoken.**
  For example "ನಾನು ಇಂದು office ಗೆ ಹೋಗಬೇಕು because I have a meeting." keeps the
  Kannada in Kannada script and the English words in English.
- This uses Sarvam's own documented mechanism - the `codemix` output mode of
  the speech-to-text API - not a second model, a second API, or a separate
  language-detection step.
- **Audio language = Auto** is now the recommended setting for mixed speech.
  Previously Auto left the language unspecified; it now explicitly asks Sarvam
  to determine the language *and* return code-mixed output, so an utterance is
  no longer forced into a single language. Choosing a specific language still
  gives normal single-language transcription.
- Speech-to-text now uses Sarvam's current models (`saaras:v3` default, or
  `saaras:v4`); the retired `saarika:*` models were removed.
- Code-switching can be turned off in Advanced settings if you prefer plain
  single-language transcription.
- NVDA no longer announces a detected language after transcribing: for mixed
  speech a single language name is misleading, and repeating it is just noise.
  You simply get the transcript.

## [1.0.6] - 2026-08-07

Makes the text to speech sliders speak, and fixes speech sounding flat.

### Bug fixes
- **The sliders now announce what they are.** They were built with a plain
  wx.Slider, which does not reliably report its name or value changes to a
  screen reader - so NVDA said nothing useful. They now use NVDA's own
  accessible slider (`nvdaControls.EnhancedInputSlider`), which sends the
  required value-change events. Arrow keys move by 5, Page Up/Down by 25.
- Slider labels now state their meaning and direction, for example
  "Speech speed in percent, 50 is slowest and 200 is fastest" and
  "Expression in percent, 5 is flat and monotonous and 100 is most lively".

### Improvements
- **Speech no longer sounds monotonous by default.** The default speaking style
  is now **Conversational** with expression raised to 80% (it was News reader at
  30%, which is deliberately flat). Expression was increased across every style.
- **Speaking styles now describe how they sound**, so the effect is clear before
  you choose: Conversational (natural everyday speech), Narration (warm
  storytelling, for books and articles), Expressive (most lively), News reader
  (crisp and steady, less emotion), Formal (measured and neutral).

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
