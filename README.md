# Sarvam AI assistant for NVDA

![Sarvam AI assistant for NVDA — accessible AI for the blind and visually impaired](docs/hero.svg)

> **Available in the official NVDA Add-on Store.** Open NVDA → Tools → Add-on
> Store → Available add-ons and search for *Sarvam AI assistant*.

An accessible NVDA add-on that brings the [Sarvam AI](https://www.sarvam.ai/)
platform to blind and low-vision users through a fully keyboard-driven,
screen-reader-friendly interface that feels native to NVDA.

## Who this is for — and why it matters

This add-on is built **for blind and visually-impaired (VI) users**, and for the
Indian-language accessibility community in particular.

- **Independence.** Powerful AI — natural speech, transcription, translation,
  document reading (OCR) and reasoning — reachable entirely by keyboard and
  screen reader, with no sighted assistance and no inaccessible web dashboards.
- **Indian languages first.** Most assistive AI targets English and Western
  markets. Sarvam is India's most comprehensive language-AI platform, so blind
  users get high-quality speech, OCR and translation across **23 Indian
  languages** — including code-mixed text — right inside NVDA.
- **Read anything.** Turn scanned PDFs, images and photographed documents into
  text with OCR, then have it spoken, translated or summarised — a common
  barrier for VI users made routine.
- **An AI workforce at your fingertips.** The new AI Workforce uses Sarvam's
  105B reasoning model to help with research, writing, coding, planning,
  studying and multi-step tasks — presented in one accessible dialog.
- **Accessible by design, not as an afterthought.** Standard NVDA controls,
  logical focus order, spoken status, a cancellable progress dialog, and
  Escape-to-exit everywhere. Nothing freezes NVDA.
- **Free and open source (GPL v2).** No lock-in; you bring your own Sarvam API
  key.

## Features

- **Text to Speech** – synthesise natural speech from typed/pasted text or an
  uploaded **text, Word (.docx) or EPUB** file; pick voice, style, gender,
  language (auto-detect), speed and pitch; play and save as **MP3 or WAV**.
- **Speech to Text** – transcribe an audio file or your microphone, with an
  optional translate-to-English mode; save as **.txt or .docx**.
- **Translation & Transliteration** – convert between English and Indian
  languages, with selectable styles.
- **Language Detection** – identify the language and script of any text.
- **AI Assistant** – chat, summarise text and understand documents.
- **AI Workforce (Sarvam-105B)** – a reasoning / agentic layer: choose a worker
  role (researcher, writer, coder, planner, analyst, tutor, task agent…), a
  reasoning effort (low/medium/high) and optional wiki grounding, then hand it a
  task. Save the result as **.txt or .docx**.
- **OCR** – recognise text from PDFs and images using **Sarvam Document OCR**
  (23 languages), or the offline **Windows OCR** engine for instant screen
  reading; then translate or summarise the result with Sarvam.

> **On OCR:** The primary OCR engine is Sarvam's Document Digitization API,
> which recognises 23 languages from a PDF or image. Because that API works on
> PDFs, the add-on automatically wraps images (and screen/clipboard captures)
> into a one-page PDF before sending them. A second, fully offline **Windows
> OCR** engine is also available for instant screen and object recognition.
> Recognised text can then be translated or summarised with Sarvam.

## Requirements

- NVDA 2021.1 or later (tested up to 2025.1).
- Windows 10 / 11.
- A Sarvam AI API key – get one from the
  [Sarvam dashboard](https://dashboard.sarvam.ai/). Note that most endpoints
  consume account credits.
- For OCR: a Windows OCR language pack (most Windows installations include
  English by default).

## Installation

1. Download the latest `SarvamAIassistant-x.y.z.nvda-addon` from the
   [Releases page](https://github.com/rakeshhonisty/Sarvam-AI-assistant/releases)
   (or build it yourself – see below).
2. In NVDA, open the **Add-on Store** (or **Tools → Manage add-ons**), choose
   **Install from external file**, and select the downloaded file.
3. Restart NVDA when prompted.

## First-time setup

1. Open **NVDA menu → Tools → Sarvam AI → Settings…** (or NVDA **Preferences →
   Settings → Sarvam AI**).
2. Paste your **Sarvam API key**.
3. Press **Validate key / Test connection**. You should hear a confirmation
   listing the available models. If you hear *"no credits available"*, your key
   is valid but your account needs credits.
4. Adjust the default voice, language, speech rate and folders to taste, then
   press **OK**.

## Using the add-on

Everything is reachable from **Tools → Sarvam AI** in the NVDA menu:

| Menu item | What it does |
|-----------|--------------|
| Text to Speech… | Synthesise and play/save speech. |
| Speech to Text… | Transcribe a file or the microphone. |
| Translate… / Transliterate… / Detect language… | Text language tools. |
| OCR… | Recognise text from a PDF/image (Sarvam OCR) or the screen (Windows OCR). |
| AI Assistant / Summarise… | Chat, summarise, or understand a document. |
| AI Workforce (reasoning, 105B)… | Reasoning/agentic tasks via Sarvam-105B with role, effort and grounding. |
| Settings… | Configure the add-on. |
| Logs… | View / export the add-on log. |
| Check for updates… | Check GitHub for a newer release. |
| Help… / About… | Documentation and version info. |

### Keyboard shortcuts

- **`NVDA+Alt+S`** — open the Sarvam AI menu (default). From there, use the arrow
  keys to reach any feature.

All other commands are unbound by default. Assign your own in
**NVDA → Preferences → Input Gestures → Sarvam AI** (open Text to Speech, speak
current selection, open Speech to Text, translate selection, open OCR, recognise
the current screen/object, open the AI assistant, open settings). You can also
rebind `NVDA+Alt+S` there.

> NVDA keyboard commands are single chords, so a combination like "NVDA+S+A"
> (two letter keys at once) isn't possible; `NVDA+Alt+S` is used instead.

## Building from source

No third-party build tools are required – a `.nvda-addon` is just a ZIP.

```bash
python build.py            # build and copy the package to your Downloads folder
python build.py --no-copy  # build only
python build.py --pot      # regenerate the translation template
```

The packaged add-on appears in the repository root and (by default) in your
`Downloads` folder.

## Accessibility

This add-on is designed accessibility-first: labelled controls, logical focus
order, standard NVDA dialogs, spoken status messages, a cancellable and
announced progress dialog, and no custom inaccessible widgets. All long-running
network calls run on background threads so NVDA never freezes.

## Privacy & security

- Your API key is stored in NVDA's configuration, lightly **obfuscated** (not
  clear text). This is obfuscation, not strong encryption – treat the machine
  as trusted.
- Text, audio, images and documents you process are sent to Sarvam's servers
  for processing (including Sarvam Document OCR). If you instead choose the
  **Windows OCR** engine, recognition happens locally on your PC and only the
  resulting text is sent to Sarvam when you ask to translate or summarise it.

## License

Released under the **GNU General Public License, version 2**. See
[LICENSE](LICENSE).

## Author and contact

Created by **Rakesh**.

- Email: <rakesh.honistyboy@gmail.com>
- Repository: <https://github.com/rakeshhonisty/Sarvam-AI-assistant>
- Issues / feature requests: <https://github.com/rakeshhonisty/Sarvam-AI-assistant/issues>

## Credits

Built for the NVDA screen reader. Sarvam AI and its API are the property of
Sarvam AI. This is an independent community add-on, not affiliated with or
endorsed by Sarvam AI or NV Access.
