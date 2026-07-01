# Sarvam API reference (as used by this add-on)

All endpoints are on `https://api.sarvam.ai` and authenticate with the header
`api-subscription-key: <YOUR_KEY>`. Verified against the live API and the
published OpenAPI specification (`https://docs.sarvam.ai/openapi.json`) on
2026-07-01. Errors use the envelope
`{"error": {"message": ..., "code": ..., "request_id": ...}}`.

> Credits: every processing endpoint consumes account credits. A valid key with
> an empty balance returns `insufficient_quota_error` (HTTP 402 or 429).

## Real-time endpoints

| Method & path | Purpose | Key fields |
|---|---|---|
| `POST /text-to-speech` | Text → speech | `text`, `target_language_code`, `speaker`, `model` (`bulbul:v2`), `pitch`, `pace`, `loudness`, `speech_sample_rate` → `{ "audios": ["<base64 wav>"] }` |
| `POST /text-to-speech/stream` | Streaming TTS | as above, streamed audio |
| `POST /speech-to-text` | Audio → text | multipart `file`, `model` (`saarika:v2.5`), `language_code` → `{ "transcript", "language_code" }` |
| `POST /speech-to-text-translate` | Audio → English text | multipart `file`, `model` (`saaras:v2.5`) |
| `POST /translate` | Text translation | `input`, `source_language_code`, `target_language_code`, `model` (`sarvam-translate:v1`), `mode` |
| `POST /transliterate` | Transliteration | `input`, `source_language_code`, `target_language_code` |
| `POST /text-lid` | Language identification | `input` → `{ "language_code", "script_code" }` |
| `POST /v1/chat/completions` | LLM chat (OpenAI-compatible) | `model` (`sarvam-105b`, `sarvam-30b`), `messages` (text only) |
| `GET /v1/models` | List chat models | — (also a lightweight auth/connectivity check) |

## Batch (job) endpoints

All batch services share the lifecycle: **create → upload-files → start →
status (poll) → download-files**, under `/{service}/job/v1`.

- `POST /speech-to-text/job/v1`
- `POST /speech-to-text-translate/job/v1`

## Document OCR (Document Digitization)

Sarvam's OCR is the **document-digitization** service. It is job-based and works
on a single **PDF** (or ZIP) per job; images are wrapped into a one-page PDF by
this add-on before upload.

| Step | Method & path | Notes |
|---|---|---|
| 1. Create | `POST /doc-digitization/job/v1` | body `{"job_parameters": {"language": "en-IN", "output_format": "md"}}` → `{ "job_id", "storage_container_type", "job_state" }` |
| 2. Upload URL | `POST /doc-digitization/job/v1/upload-files` | body `{"job_id", "files": ["doc.pdf"]}` → `{ "upload_urls": { "doc.pdf": {"file_url": ...} } }` |
| 3. Upload | `PUT <file_url>` | raw PUT of the PDF bytes; Azure requires `x-ms-blob-type: BlockBlob` |
| 4. Start | `POST /doc-digitization/job/v1/{job_id}/start` | 202 |
| 5. Status | `GET /doc-digitization/job/v1/{job_id}/status` | poll until `job_state` ∈ {`Completed`, `PartiallyCompleted`, `Failed`} |
| 6. Download | `POST /doc-digitization/job/v1/{job_id}/download-files` | → `{ "download_urls": { name: {"file_url": ...} } }`; the file is a **ZIP** of `md`/`html`/`json` output |

### OCR parameters

- `language` (**not** `language_code`): one of 23 codes — note Odia is `or-IN`
  here (the TTS/translate APIs use `od-IN`).
- `output_format`: `md` (Markdown — not `markdown`), `html`, or `json`.

## Language codes

`en-IN`, `hi-IN`, `bn-IN`, `gu-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`/`or-IN`
(Odia; OCR uses `or-IN`), `pa-IN`, `ta-IN`, `te-IN`. Document OCR adds `ur-IN`,
`as-IN`, `sa-IN`, `ne-IN`, `kok-IN`, `mai-IN`, `sd-IN`, `ks-IN`, `doi-IN`,
`mni-IN`, `bodo-IN`, `sat-IN`.

## TTS voices

`bulbul:v2`: `anushka`, `manisha`, `vidya`, `arya`, `abhilash`, `karun`,
`hitesh`.
