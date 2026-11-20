# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.
# See the file LICENSE for more details.

"""Central catalogue of Sarvam AI endpoints, languages and file formats.

Every network-facing constant lives here (models live in :mod:`models`) so
that, when Sarvam changes a path, there is exactly one place to update.
Updated for Sarvam AI assistant 2.0 against the Sarvam documentation on
2026-11-20.
"""

from . import models as _models

ADDON_NAME = "sarvamAI"
ADDON_SUMMARY = "Sarvam AI assistant"

# Default API host. Overridable from the settings panel (advanced).
DEFAULT_BASE_URL = "https://api.sarvam.ai"

# Official Sarvam developer portal, where users create their own API key.
SARVAM_DASHBOARD_URL = "https://dashboard.sarvam.ai/"

# The HTTP header carrying the subscription key.
AUTH_HEADER = "api-subscription-key"

# --- Endpoint paths ----------------------------------------------------------
EP_TEXT_TO_SPEECH = "/text-to-speech"
EP_TTS_STREAM = "/text-to-speech/stream"
EP_SPEECH_TO_TEXT = "/speech-to-text"
EP_TRANSLATE = "/translate"
EP_TRANSLITERATE = "/transliterate"
EP_TEXT_LID = "/text-lid"

# Chat. V2 serves Sarvam 105B and all the open models (GLM, Gemma, DeepSeek,
# Kimi, Qwen) and supports tools, images and structured output. V1 is legacy
# and only used as a fallback for Sarvam 105B.
EP_CHAT_COMPLETIONS = "/v2/chat/completions"
EP_CHAT_COMPLETIONS_V1 = "/v1/chat/completions"
EP_MODELS = "/v2/models"
EP_MODELS_V1 = "/v1/models"

# Batch speech to text (long audio, up to 2 hours per file, diarization).
EP_STT_JOB = "/speech-to-text/job/v1"
EP_STT_JOB_UPLOAD = "/speech-to-text/job/v1/upload-files"
EP_STT_JOB_START = "/speech-to-text/job/v1/{job_id}/start"
EP_STT_JOB_STATUS = "/speech-to-text/job/v1/{job_id}/status"
EP_STT_JOB_DOWNLOAD = "/speech-to-text/job/v1/download-files"

# Real-time /speech-to-text handles up to 30 s clips; larger audio uses the
# batch job API. This size threshold (bytes) is a safe switch-over point.
STT_REALTIME_MAX_BYTES = 900 * 1024
# Terminal states shared by the batch job APIs (Title Case on these APIs).
JOB_TERMINAL_STATES = ("Completed", "PartiallyCompleted", "Failed")

# Document AI (Sarvam Vision 2.1) - the current document engine.
EP_DOCAI_PARSE = "/doc-ai/v1/job/parse"
EP_DOCAI_EXTRACT = "/doc-ai/v1/job/extract"
EP_DOCAI_STATUS = "/doc-ai/v1/job/{job_id}/status"
EP_DOCAI_RESULTS = "/doc-ai/v1/job/{job_id}/results"
EP_DOCAI_DOWNLOAD_URL = "/doc-ai/v1/job/{job_id}/download-url"
# Document AI job statuses are lower case.
DOCAI_DONE_STATES = ("completed", "partially_completed")
DOCAI_FAILED_STATES = ("failed", "rejected")
# Inputs Document AI accepts directly. Other images are wrapped into a PDF.
DOCAI_DIRECT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".zip")

# Legacy document digitization (kept as an automatic fallback only).
EP_OCR_CREATE = "/doc-digitization/job/v1"
EP_OCR_UPLOAD = "/doc-digitization/job/v1/upload-files"
EP_OCR_START = "/doc-digitization/job/v1/{job_id}/start"
EP_OCR_STATUS = "/doc-digitization/job/v1/{job_id}/status"
EP_OCR_DOWNLOAD = "/doc-digitization/job/v1/{job_id}/download-files"
OCR_TERMINAL_STATES = ("Completed", "PartiallyCompleted", "Failed")

# Document translation: translate a whole file and get it back in the same
# format, with its layout kept.
EP_DOCTR_CREATE = "/translate/document/jobs"
EP_DOCTR_START = "/translate/document/jobs/{job_id}/start"
EP_DOCTR_STATUS = "/translate/document/jobs/{job_id}/live-status"
EP_DOCTR_EXPORT = "/translate/document/jobs/{job_id}/export"
EP_DOCTR_EXPORT_STATUS = "/translate/document/jobs/{job_id}/export/status"
DOCTR_EXTENSIONS = (
	".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods",
	".ppt", ".pptx", ".odp", ".html", ".htm", ".xhtml", ".mhtml",
	".md", ".markdown", ".txt")
DOCTR_GENRES = ("", "NON_FICTION", "ADULT_FICTION", "CHILDREN_FICTION",
	"RELIGIOUS", "LEGAL", "ACADEMIC")

# Document output formats (delivered inside a ZIP). "md" = Markdown (not
# "markdown", which the API rejects).
OCR_OUTPUT_FORMATS = ("md", "html", "json")
DEFAULT_OCR_OUTPUT_FORMAT = "md"

# The 23 document languages. Document AI uses "od-IN" for Odia and "brx-IN"
# for Bodo; the legacy API used "or-IN" and "bodo-IN" (mapped automatically).
OCR_LANGUAGES = {
	"en-IN": "English (India)",
	"hi-IN": "Hindi",
	"bn-IN": "Bengali",
	"gu-IN": "Gujarati",
	"kn-IN": "Kannada",
	"ml-IN": "Malayalam",
	"mr-IN": "Marathi",
	"od-IN": "Odia",
	"pa-IN": "Punjabi",
	"ta-IN": "Tamil",
	"te-IN": "Telugu",
	"ur-IN": "Urdu",
	"as-IN": "Assamese",
	"brx-IN": "Bodo",
	"doi-IN": "Dogri",
	"ks-IN": "Kashmiri",
	"kok-IN": "Konkani",
	"mai-IN": "Maithili",
	"mni-IN": "Manipuri",
	"ne-IN": "Nepali",
	"sa-IN": "Sanskrit",
	"sat-IN": "Santali",
	"sd-IN": "Sindhi",
}
LEGACY_OCR_LANGUAGE_MAP = {"od-IN": "or-IN", "brx-IN": "bodo-IN"}
DEFAULT_OCR_LANGUAGE = "auto"
OCR_AUTO_LANGUAGE = "auto"

# OCR engine identifiers (kept for backward-compatible config values).
OCR_ENGINE_SARVAM = "sarvam"
OCR_ENGINE_WINDOWS = "windows"

# Document AI extract output formats.
EXTRACT_OUTPUT_FORMATS = ("csv", "xlsx", "json")
EXTRACT_MODES = ("basic", "advanced")

# --- Model shortcuts (the catalogue lives in models.py) ----------------------
TTS_MODELS = _models.tts_ids()
STT_MODELS = _models.stt_ids()
TRANSLATE_MODELS = _models.translate_ids()
CHAT_MODELS = _models.chat_ids()
DEFAULT_TTS_MODEL = _models.DEFAULT_TTS_MODEL
DEFAULT_STT_MODEL = _models.DEFAULT_STT_MODEL
DEFAULT_TRANSLATE_MODEL = _models.DEFAULT_TRANSLATE_MODEL
DEFAULT_CHAT_MODEL = _models.DEFAULT_CHAT_MODEL
DEFAULT_VISION_MODEL = _models.DEFAULT_VISION_MODEL
WORKFORCE_MODEL = _models.DEFAULT_CHAT_MODEL

# Retained only so settings saved by 1.x still validate; never sent any more.
STT_TRANSLATE_MODELS = ("saaras:v2.5",)
DEFAULT_STT_TRANSLATE_MODEL = "saaras:v2.5"

# Audio codecs. "opus" is rejected by /text-to-speech for v3/v4, so it is not
# offered. "wav" is used for in-app playback.
TTS_OUTPUT_CODECS = ("mp3", "wav", "flac", "aac")
DEFAULT_TTS_CODEC = "mp3"
AUDIO_SAVE_FORMATS = (
	("mp3", "MP3 audio (*.mp3)"),
	("wav", "WAV audio (*.wav)"),
	("flac", "FLAC lossless audio (*.flac)"),
	("aac", "AAC audio (*.aac)"),
)

# Output modes supported by /speech-to-text (saaras:v3 / v4).
STT_MODES = ("transcribe", "translate", "verbatim", "translit", "codemix")
STT_MODE_LABELS = {
	"transcribe": "Transcribe in the spoken language",
	"translate": "Translate the speech to English",
	"verbatim": "Verbatim, word for word",
	"translit": "Romanised (Latin script)",
	"codemix": "Code-mixed (English words stay English)",
}
DEFAULT_STT_MODE = "transcribe"
STT_CODEMIX_MODE = "codemix"
STT_AUTO_LANGUAGE = "unknown"
# Key terms (saaras:v4): up to 50 terms of up to 64 characters.
STT_MAX_KEYTERMS = 50
STT_MAX_KEYTERM_CHARS = 64

# --- Reasoning ---------------------------------------------------------------
REASONING_EFFORTS = ("none", "low", "medium", "high", "max")
DEFAULT_REASONING_EFFORT = "medium"

# --- AI Workforce task modes ---------------------------------------------------
# Each is (key, English label, system prompt). "agent" and "vision" switch on
# the agentic tool loop and image understanding respectively.
WORKFORCE_ROLES = (
	("assistant", "AI Assistant",
		"You are a highly capable, helpful AI assistant. Think step by step and "
		"give a clear, accurate, well-structured answer."),
	("agent", "Agent - does the work for you (translate, speak, save files)",
		"You are an autonomous assistant inside a screen reader add-on used by blind "
		"and visually impaired people. You can call tools to translate, "
		"transliterate, detect languages, read the attached files, create speech "
		"audio files and save documents in any format. Plan briefly, call the "
		"tools you need one step at a time, check each result, and finish with a "
		"short plain-language summary of what you did, including the names of any "
		"files you saved. Never invent file contents you have not read."),
	("vision", "Describe images and screenshots",
		"You describe images for a blind person. Start with a one sentence summary, "
		"then describe layout, text (read every visible word exactly), people, "
		"objects, colours and anything important for understanding or action. "
		"Be factual; say when something is unclear."),
	("summary", "AI Summary",
		"Summarise the provided material clearly and concisely, preserving the "
		"key facts, structure and any figures. Use headings or bullet points "
		"where that aids clarity."),
	("document", "Document Analysis",
		"You are a document analyst. Read the provided document carefully, "
		"extract the key points, structure and entities, and answer the user's "
		"question about it with your reasoning made explicit."),
	("content", "Content Generation",
		"You are a professional writer. Generate high-quality, well-structured, "
		"polished content exactly as requested (drafts, emails, reports, posts, "
		"articles), ready to use."),
	("qa", "Question Answering",
		"Answer the user's question accurately and directly, using the provided "
		"context where given and your own knowledge otherwise. Be precise."),
	("workforce", "General AI Workforce",
		"You are a capable multi-step task agent. State a brief plan, carry it "
		"out step by step, then give the final result clearly."),
)
DEFAULT_WORKFORCE_ROLE = "assistant"
AGENT_ROLE = "agent"
VISION_ROLE = "vision"
AGENT_MAX_STEPS = 8

# --- Batch / parallel processing --------------------------------------------
BATCH_MULTIPLIERS = ("1x", "2x", "3x", "4x", "5x", "10x")
DEFAULT_BATCH_MULTIPLIER = "2x"


def batch_multiplier_value(label):
	"""Turn a "3x" label into the integer 3 (bounded 1..16)."""
	try:
		return max(1, min(16, int(str(label).lower().rstrip("x"))))
	except (ValueError, TypeError):
		return 1


# --- Speakers ---------------------------------------------------------------
# The authoritative catalogues live in ttsstyles.
DEFAULT_SPEAKER = "shubh"

# --- Languages --------------------------------------------------------------
# Text to speech, Mayura translation and transliteration languages.
LANGUAGES = {
	"en-IN": "English (India)",
	"hi-IN": "Hindi",
	"bn-IN": "Bengali",
	"gu-IN": "Gujarati",
	"kn-IN": "Kannada",
	"ml-IN": "Malayalam",
	"mr-IN": "Marathi",
	"od-IN": "Odia",
	"pa-IN": "Punjabi",
	"ta-IN": "Tamil",
	"te-IN": "Telugu",
}

# Extra languages handled by Sarvam-Translate (22 scheduled languages) and by
# speech to text.
EXTRA_LANGUAGES = {
	"as-IN": "Assamese",
	"brx-IN": "Bodo",
	"doi-IN": "Dogri",
	"ks-IN": "Kashmiri",
	"kok-IN": "Konkani",
	"mai-IN": "Maithili",
	"mni-IN": "Manipuri",
	"ne-IN": "Nepali",
	"sa-IN": "Sanskrit",
	"sat-IN": "Santali",
	"sd-IN": "Sindhi",
	"ur-IN": "Urdu",
}
ALL_LANGUAGES = dict(LANGUAGES, **EXTRA_LANGUAGES)

# For source language of translation / transliteration "auto" is accepted.
AUTO_DETECT = "auto"

# Fallback used when auto-detection cannot map to a supported TTS language.
DEFAULT_TTS_FALLBACK_LANGUAGE = "en-IN"


def language_name(code):
	return ALL_LANGUAGES.get(code, code)


def to_tts_language(detected_code):
	"""Map a language code from /text-lid to a supported TTS language code.

	Handles the Odia code difference (text-lid may return ``or-IN`` while TTS
	uses ``od-IN``) and falls back to English (India) for anything the TTS
	models do not support.
	"""
	if not detected_code:
		return DEFAULT_TTS_FALLBACK_LANGUAGE
	code = detected_code.strip()
	if code in ("or-IN", "ory-IN"):
		code = "od-IN"
	if code in LANGUAGES:
		return code
	primary = code.split("-")[0].lower()
	for supported in LANGUAGES:
		if supported.split("-")[0].lower() == primary:
			return supported
	return DEFAULT_TTS_FALLBACK_LANGUAGE


# Translation output styles accepted by /translate (Mayura).
TRANSLATE_MODES = ("formal", "modern-colloquial", "classic-colloquial", "code-mixed")
DEFAULT_TRANSLATE_MODE = "formal"

# Speaker gender hint for translation.
SPEAKER_GENDERS = ("Male", "Female")

# Numerals formatting for translate / transliterate.
NUMERALS_FORMATS = ("international", "native")

# Output script options for translate.
OUTPUT_SCRIPTS = ("", "roman", "fully-native", "spoken-form-in-native")

# --- Audio ------------------------------------------------------------------
TTS_SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)
DEFAULT_TTS_SAMPLE_RATE = 24000

# bulbul:v3 and v4-flash accept pace 0.5-2.0 and temperature 0.01-1. Neither
# supports pitch or loudness (HTTP 400 if sent).
PACE_RANGE = (0.5, 2.0)
TEMPERATURE_RANGE = (0.05, 1.0)

# Recognised audio extensions for speech to text.
AUDIO_EXTENSIONS = (
	".wav", ".mp3", ".m4a", ".mp4", ".aac", ".aiff", ".aif", ".flac", ".ogg",
	".opus", ".webm", ".amr", ".wma")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp")
# Inputs accepted by the document engine (PDF, images, ZIP of page images).
OCR_INPUT_EXTENSIONS = (".pdf", ".zip") + IMAGE_EXTENSIONS

# Maximum characters per TTS request (2500 for bulbul v3 / v4-flash).
TTS_MAX_CHARS = 2500

# Maximum characters sent to /translate per request (Mayura allows 1000,
# Sarvam-Translate 2000); longer input is split and re-joined.
TRANSLATE_MAX_CHARS = 1800
