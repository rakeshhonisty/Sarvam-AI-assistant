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

## What's new in 2.0 ("sarvamAI-2.0")

- **New and open models, plus Model switching.** Sarvam 105B, plus Sarvam's hosted
  open models: GLM 5.3 and GLM 5.3 Flash, Gemma 4, DeepSeek V4.1 Flash, and
  (with Provisioned Throughput) DeepSeek V4 Pro, Kimi K3.1 Pro and Qwen 3.8.
  Bulbul v4 Flash voices and Saaras v4 speech recognition. One **Model
  switching** window chooses the model for every feature and says what each
  one can do.
- **Sarvam Agent.** It does multi-step work for you, such as translating, making
  speech files and saving documents, and tells you each step.
- **AI vision.** It describes photos, screenshots and the current screen.
- **Upload almost any file. Download in the format you want.** Word, Markdown,
  HTML, RTF, Excel, CSV, JSON, text, SRT subtitles, and MP3/WAV/FLAC/AAC audio.
- **Whole-document translation that keeps the format** (PDF, Word, Excel,
  PowerPoint, HTML).
- **Data extraction to spreadsheets.** Describe the fields in plain words and
  download them as Excel or CSV.

See the [CHANGELOG](CHANGELOG.md) for the full list.

## Features

- **Text to Speech**: speak typed or pasted text, or an uploaded file of almost
  any type. You pick a voice in steps, **Voice model → Language → Gender →
  Purpose (nature of work) → Voice**. Purposes include news, narration and
  audiobooks, customer support and banking, education and children, ads and
  social media, devotional, drama, companion, sports and more. Both
  **Bulbul v4 Flash** (222 persona voices) and **Bulbul v3** (37 voices) use
  this classification. Malayalam and Odia switch to v3 automatically. Speed
  and Expression sliders. **Listen**, then **Download** as MP3, WAV, FLAC or AAC.
- **Speech to Text (Saaras v4)**: transcribe a file or the microphone. Output
  in the spoken language, English, verbatim, romanised or code-mixed.
  **Key terms** help it spell names correctly. It can **separate speakers** and
  add **timings** for SRT subtitles. Long audio (up to 2 hours) uses the batch
  API automatically.
- **Translation, Transliteration and Language detection**: one dialog with an
  **Operation** list. Upload any file to translate its text, or **translate a
  whole document and keep its format**. **Sarvam-Translate** covers all 22
  scheduled Indian languages. Mayura offers formal, colloquial and code-mixed
  styles.
- **Documents and OCR (Sarvam Document AI)**: read PDFs, scans, photos and
  ZIPs of page images in 23 languages, keeping headings, tables, columns and
  reading order. Or **extract data**: describe what you need and download it as
  Excel, CSV or JSON.
- **AI Workforce and Agent**: assistant, agent, image description, summary,
  document analysis, content generation and question answering. You can attach
  several files, switch models, set the reasoning level and ask follow-up
  questions.
- **Download formats everywhere**: once a task succeeds, a **Download format**
  list and a **Download** button appear. Markdown tables become real tables in
  Word, HTML and Excel.
- **Accessibility-first**: download options appear only once a task succeeds.
  Escape closes any window from anywhere, every control is labelled, and no
  long task ever blocks NVDA.

## Requirements

- NVDA 2021.1 or later (tested up to 2026.1).
- Windows 10 / 11.
- A Sarvam AI API key – press **Generate API key** in the add-on's settings, or
  get one from the [Sarvam dashboard](https://dashboard.sarvam.ai/). Note that
  Sarvam endpoints consume account credits.

## Installation

1. Download the latest `sarvamAI-x.y.z.nvda-addon` from the
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
   (No key yet? Press **Generate API key** to open the Sarvam developer portal.)
4. Adjust your defaults, then press **Save**. More options live under
   **Advanced settings**, including **Batch processing speed (1x–10x)**.

## Using the add-on

Everything is reachable from **Tools → Sarvam AI** in the NVDA menu:

| Menu item | What it does |
|-----------|--------------|
| Text to Speech… | Synthesise, play and download speech (voice classification by gender, purpose, language). |
| Speech to Text… | Transcribe a file or the microphone; speakers, timings, key terms. |
| Translate… / Transliterate… / Detect language… | Text tools, plus whole-document translation that keeps the format. |
| Documents and OCR… | Sarvam Document AI: read documents, or extract data to Excel/CSV/JSON. |
| AI Workforce… | Assistant, summary, analysis, content, Q&A, with any model. |
| Sarvam Agent… | Multi-step tasks done for you with tools (translate, speak, save files). |
| Describe the screen with AI vision | Describes the current window. |
| Model switching… | Choose the model behind every feature. |
| Settings (API key)… | API key, Generate API key, and core defaults. |
| Advanced settings… | All options, including batch processing speed. |
| Logs… | View / export the add-on log. |
| Check for updates… | Check GitHub for a newer release. |
| Help… / About… | Documentation and version info. |

### Keyboard shortcuts

No shortcut is bound by default, so nothing clashes with NVDA's own commands
(an earlier default clashed with NVDA's sound-split command). Assign your own in
**NVDA → Preferences → Input Gestures → Sarvam AI** — for example "Opens the
Sarvam AI menu", or go straight to Text to Speech, Speech to Text, Translate,
OCR, AI Workforce, the Agent, Model switching, "Describe the current window",
"Describe the whole screen" or "Switch to the next chat model".

Inside any Sarvam AI window, **Escape closes it** — even from inside a text box.

## Building from source

No third-party build tools are required – a `.nvda-addon` is just a ZIP.

```bash
python build.py            # build and copy the package to your Downloads folder
python build.py --no-copy  # build only
python build.py --pot      # regenerate the translation template
```

The packaged add-on appears in the repository root and (by default) in your
`Downloads` folder.

Run the tests (no NVDA needed; NVDA and wx are stubbed):

```bash
python -m unittest discover -s tests -v
```

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
  for processing (including Sarvam Document AI). The screen is captured and
  sent only when you run "Describe the screen". Nothing is sent anywhere else,
  and the add-on itself collects no data.
- Open models (GLM, Gemma, DeepSeek, Kimi, Qwen) are hosted by Sarvam on its
  India-based inference platform; your requests go to Sarvam, as with Sarvam
  105B.
- The Agent can read only the files you attach and can write only new files
  into your output folder. It never overwrites or deletes files, and it cannot
  run programs.

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
