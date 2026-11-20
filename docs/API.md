# Sarvam API reference (as used by this add-on, version 2.0)

All endpoints are on `https://api.sarvam.ai` and authenticate with the header
`api-subscription-key: <YOUR_KEY>`. Checked against the Sarvam documentation
(`https://docs.sarvam.ai/openapi/apis.json`, the model guides and the
changelog) on 2026-11-20. The model catalogue lives in
`addon/globalPlugins/sarvamAI/models.py`; endpoints live in `constants.py`.

> Credits: every processing endpoint consumes account credits. A valid key with
> an empty balance returns `insufficient_quota_error` (HTTP 402 or 429). Auth
> failures are HTTP 403.

## Chat - `POST /v2/chat/completions`

OpenAI-compatible. Used by the AI Workforce, the Agent, vision and data
extraction (schema building).

| Model id | Notes |
|---|---|
| `sarvam-105b` | Sarvam flagship, 128K context. Falls back to `/v1/chat/completions` if V2 is refused. |
| `glm5.3-flash` | 1M context, images. Reasoning `low` / `high` only. |
| `glm5.3` | 1M context. Reasoning `low` / `high` only. |
| `gemma4` | Gemma 4 31B, 262K context, images. Thinks only when `reasoning_effort` is sent. |
| `deepseekv4.1-flash-1017` (+ `-interactive`) | 1M context, images. `none` turns thinking off. |
| `deepseekv4-pro`, `kimi-k3.1-pro`, `qwen38-27b` | Provisioned Throughput only. |

Retired: `sarvam-m`, `sarvam-30b`, `sarvam-30b-16k`, `sarvam-105b-32k`, `kimi-k3`,
`mimo-v2.6-*`.

Fields used: `model`, `messages` (content is a string or `text` / `image_url`
parts; images must be inline `data:` URLs), `reasoning_effort`
(`none`/`low`/`medium`/`high`/`max`, per model), `max_tokens`, `temperature`,
`tools` (`type: function`), `tool_choice` (`auto`), `response_format`
(`json_object` for schema building). The response's `choices[0].message`
carries `content`, `tool_calls` and `reasoning_content`. A request body can be
at most 10 MB.

`GET /v2/models` returns `{"data": [{"id", "owned_by", "access"}]}`. It is used
for "Check which models my key can use" and as the connection test.

## Text to speech - `POST /text-to-speech`

`text` (up to 2500 characters; the add-on chunks longer text),
`target_language_code`, `speaker`, `model` (`bulbul:v4-flash` or
`bulbul:v3`), `pace` (0.5-2.0), `temperature` (0.01-1.0),
`speech_sample_rate` (8000-48000), `output_audio_codec` (`wav` for playback;
`mp3`, `flac`, `aac` for downloads). The response is `{"audios": ["<base64>"]}`.

- `pitch`, `loudness` and `enable_preprocessing` are bulbul:v2-only and are
  rejected or ignored by v3 and v4-flash, so they are never sent.
- `bulbul:v4-flash` has 222 persona voices named `<name>_<lang>_<purpose>`, for
  example `ritu_hi_banking`. Its languages are hi, en, Hinglish, bn, gu, kn, mr,
  pa, ta and te; there is no ml or od, so the add-on falls back to `bulbul:v3`
  for those. `bulbul:v3` has 37 voices, for example `shubh` and `ritu`.

## Speech to text

- `POST /speech-to-text` (multipart, clips up to 30 s): `file`, `model`
  (`saaras:v4` default, `saaras:v3`), `language_code` (`unknown` = auto),
  `mode` (`transcribe`, `translate`, `verbatim`, `translit`, `codemix`),
  `with_timestamps`, and `keyterms` (a JSON array, saaras:v4 only, up to 50).
- Batch: `POST /speech-to-text/job/v1` with `{"job_parameters": {model,
  language_code, mode, with_timestamps, with_diarization, num_speakers,
  keyterms}}` → `upload-files` → PUT → `{job_id}/start` → `{job_id}/status`
  (`job_state` Title Case) → `download-files` with `{"job_id", "files"}`.
  Results can include `diarized_transcript.entries[]` (`speaker_id`,
  `transcript`, `start_time_seconds`, `end_time_seconds`).
- The legacy `/speech-to-text-translate` (`saaras:v2.5`) is no longer used.

## Translation

- `POST /translate`: `input`, `source_language_code` (`auto` allowed),
  `target_language_code`, `model` (`sarvam-translate:v1`, 22 languages, 2000
  characters; or `mayura:v1`, 1000 characters, with `mode` styles).
- `POST /transliterate`, `POST /text-lid`.
- Document translation keeps the file format. `POST /translate/document/jobs`
  with `{source_language_code, target_language_codes[], original_filename,
  job_name}` returns `{job_id, upload_url}`. Then PUT the file
  (`x-ms-blob-type: BlockBlob`), `POST .../{job_id}/start`, poll
  `GET .../{job_id}/live-status` (`job_state`, `translations[]`), call
  `POST .../{job_id}/export?lang=<code>`, poll
  `GET .../{job_id}/export/status`, and finally download from `download_url`.

## Document AI (Sarvam Vision 2.1) - `/doc-ai/v1`

| Step | Call |
|---|---|
| Parse (read) | `POST /doc-ai/v1/job/parse`, multipart `file`, `language` (omitted = auto), `output_format` `md`/`html`/`json` → `{job_id}` |
| Extract | `POST /doc-ai/v1/job/extract`, multipart `file`, `schema` (JSON string), `output_format` `json`/`csv`/`xlsx`, `mode` `basic`/`advanced` |
| Status | `GET /doc-ai/v1/job/{job_id}/status` → `status`: `pending`, `running`, `completed`, `partially_completed`, `failed` or `rejected`, plus `usage.pages_total` |
| Results | `GET /doc-ai/v1/job/{job_id}/results` → parse: `documents[].pages[].content`; extract: `result` |
| File | `GET /doc-ai/v1/job/{job_id}/download-url` → `{url, headers}` (a ZIP for parse; the CSV or XLSX for extract) |

Inputs: PDF, PNG, JPEG, ZIP (a flat archive of page images). Other images are
wrapped into a one-page PDF by `imaging.py`. Languages: 23 (Odia `od-IN`, Bodo
`brx-IN`).

If Document AI answers 404 or 405, the add-on falls back to the legacy
`/doc-digitization/job/v1` flow (Odia `or-IN`, Bodo `bodo-IN`).
