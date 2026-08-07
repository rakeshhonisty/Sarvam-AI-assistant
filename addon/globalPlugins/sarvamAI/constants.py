# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.
# See the file LICENSE for more details.

"""Central catalogue of Sarvam AI endpoints, models, voices and languages.

Every network-facing constant lives here so that, when Sarvam changes a model
name or a path, there is exactly one place to update. Values verified live
against ``https://api.sarvam.ai`` on 2026-07-01.
"""

ADDON_NAME = "sarvamAI"
ADDON_SUMMARY = "Sarvam AI assistant"

# Default API host. Overridable from the settings panel (advanced).
DEFAULT_BASE_URL = "https://api.sarvam.ai"

# Official Sarvam developer portal, where users create their own API key.
SARVAM_DASHBOARD_URL = "https://dashboard.sarvam.ai/"

# The HTTP header carrying the subscription key (confirmed live).
AUTH_HEADER = "api-subscription-key"

# --- Endpoint paths (verified to exist) -------------------------------------
EP_TEXT_TO_SPEECH = "/text-to-speech"
EP_SPEECH_TO_TEXT = "/speech-to-text"
EP_SPEECH_TO_TEXT_TRANSLATE = "/speech-to-text-translate"
EP_TRANSLATE = "/translate"
EP_TRANSLITERATE = "/transliterate"
EP_TEXT_LID = "/text-lid"
EP_CHAT_COMPLETIONS = "/v1/chat/completions"
EP_MODELS = "/v1/models"
EP_TTS_STREAM = "/text-to-speech/stream"

# Batch (job) APIs. All follow the same create -> upload -> start -> status ->
# download lifecycle under /{service}/job/v1.
EP_STT_JOB = "/speech-to-text/job/v1"
EP_STT_JOB_UPLOAD = "/speech-to-text/job/v1/upload-files"
EP_STT_JOB_START = "/speech-to-text/job/v1/{job_id}/start"
EP_STT_JOB_STATUS = "/speech-to-text/job/v1/{job_id}/status"
EP_STT_JOB_DOWNLOAD = "/speech-to-text/job/v1/download-files"
EP_STT_TRANSLATE_JOB = "/speech-to-text-translate/job/v1"

# Real-time /speech-to-text handles roughly <=30 s clips; larger audio uses the
# batch job API. This size threshold (bytes) is a safe switch-over point.
STT_REALTIME_MAX_BYTES = 8 * 1024 * 1024
# Terminal states shared by the batch job APIs.
JOB_TERMINAL_STATES = ("Completed", "PartiallyCompleted", "Failed")

# Document digitization = Sarvam's OCR / document intelligence service.
EP_OCR_CREATE = "/doc-digitization/job/v1"
EP_OCR_UPLOAD = "/doc-digitization/job/v1/upload-files"
EP_OCR_START = "/doc-digitization/job/v1/{job_id}/start"
EP_OCR_STATUS = "/doc-digitization/job/v1/{job_id}/status"
EP_OCR_DOWNLOAD = "/doc-digitization/job/v1/{job_id}/download-files"

# OCR output formats (delivered inside a ZIP). "md" = Markdown (note: not
# "markdown", which the API rejects).
OCR_OUTPUT_FORMATS = ("md", "html", "json")
DEFAULT_OCR_OUTPUT_FORMAT = "md"

# OCR job states.
OCR_TERMINAL_STATES = ("Completed", "PartiallyCompleted", "Failed")

# The 23 languages supported by document digitization. Note that OCR uses
# "or-IN" for Odia (the TTS/translate APIs use "od-IN").
OCR_LANGUAGES = {
	"en-IN": "English (India)",
	"hi-IN": "Hindi",
	"bn-IN": "Bengali",
	"gu-IN": "Gujarati",
	"kn-IN": "Kannada",
	"ml-IN": "Malayalam",
	"mr-IN": "Marathi",
	"or-IN": "Odia",
	"pa-IN": "Punjabi",
	"ta-IN": "Tamil",
	"te-IN": "Telugu",
	"ur-IN": "Urdu",
	"as-IN": "Assamese",
	"bodo-IN": "Bodo",
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
DEFAULT_OCR_LANGUAGE = "auto"

# "auto" lets Sarvam determine the document language (the language hint is
# omitted from the request). Offered at the top of the OCR language list.
OCR_AUTO_LANGUAGE = "auto"

# OCR engine identifiers. Sarvam Document OCR is the only engine used now;
# the Windows constant is retained for backward-compatible config values.
OCR_ENGINE_SARVAM = "sarvam"
OCR_ENGINE_WINDOWS = "windows"

# --- Models -----------------------------------------------------------------
# Only bulbul:v3 is supported; bulbul:v2 is being deprecated by Sarvam.
TTS_MODELS = ("bulbul:v3",)

# Output audio codecs accepted by /text-to-speech (verified from OpenAPI spec).
# "wav" is used for in-app playback; "mp3" for saving a compact file.
TTS_OUTPUT_CODECS = ("mp3", "wav", "opus", "flac", "aac")
DEFAULT_TTS_CODEC = "mp3"
STT_MODELS = ("saarika:v2.5", "saarika:v2", "saarika:v1", "saarika:flash")
STT_TRANSLATE_MODELS = ("saaras:v2.5", "saaras:v2", "saaras:v1", "saaras:flash")
TRANSLATE_MODELS = ("sarvam-translate:v1", "mayura:v1")
# Chat models. sarvam-105b (128K context) is the current reasoning model.
CHAT_MODELS = ("sarvam-105b",)

# --- AI Workforce (sarvam-105b reasoning / agentic layer) -------------------
# Reasoning effort accepted by /v1/chat/completions (low/medium/high; the API
# also allows disabling by omitting it).
REASONING_EFFORTS = ("low", "medium", "high")
DEFAULT_REASONING_EFFORT = "medium"

WORKFORCE_MODEL = "sarvam-105b"

# Task modes for the unified AI Workforce (merges the former AI Assistant,
# AI Summarise and AI Workforce). Each is (key, English label, system prompt).
WORKFORCE_ROLES = (
	("assistant", "AI Assistant",
		"You are a highly capable, helpful AI assistant. Think step by step and "
		"give a clear, accurate, well-structured answer."),
	("summary", "AI Summary",
		"Summarise the provided material clearly and concisely, preserving the "
		"key facts, structure and any figures. Use headings or bullet points "
		"where that aids clarity."),
	("document", "Document Analysis",
		"You are a document analyst. Read the provided document carefully, "
		"extract the key points, structure and entities, and answer the user's "
		"question about it with your reasoning made explicit."),
	("workforce", "General AI Workforce",
		"You are a capable multi-step task agent. State a brief plan, carry it "
		"out step by step, then give the final result clearly."),
	("content", "Content Generation",
		"You are a professional writer. Generate high-quality, well-structured, "
		"polished content exactly as requested (drafts, emails, reports, posts, "
		"articles), ready to use."),
	("qa", "Question Answering",
		"Answer the user's question accurately and directly, using the provided "
		"context where given and your own knowledge otherwise. Be precise."),
	("file", "File Analysis",
		"Analyse the content of the uploaded file and perform the requested task "
		"on it, giving a structured, well-reasoned result."),
)
DEFAULT_WORKFORCE_ROLE = "assistant"

# --- Batch / parallel processing --------------------------------------------
# How many work items (e.g. long-text TTS chunks, multiple files) to process
# concurrently. Shown in Advanced settings as 1x/2x/.../10x.
BATCH_MULTIPLIERS = ("1x", "2x", "3x", "4x", "5x", "10x")
DEFAULT_BATCH_MULTIPLIER = "2x"


def batch_multiplier_value(label):
	"""Turn a "3x" label into the integer 3 (bounded 1..16)."""
	try:
		return max(1, min(16, int(str(label).lower().rstrip("x"))))
	except (ValueError, TypeError):
		return 1

DEFAULT_TTS_MODEL = "bulbul:v3"
DEFAULT_STT_MODEL = "saarika:v2.5"
DEFAULT_STT_TRANSLATE_MODEL = "saaras:v2.5"
DEFAULT_TRANSLATE_MODEL = "sarvam-translate:v1"
DEFAULT_CHAT_MODEL = "sarvam-105b"

# --- Speakers ---------------------------------------------------------------
# The authoritative bulbul:v3 speaker list lives in ttsstyles.ALL_SPEAKERS.
DEFAULT_SPEAKER = "shubh"


# --- Languages --------------------------------------------------------------
# Mapping of BCP-47-ish Sarvam language codes to human readable names.
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

# For source language of translation / transliteration "auto" is accepted.
AUTO_DETECT = "auto"

# Fallback used when auto-detection cannot map to a supported TTS language.
DEFAULT_TTS_FALLBACK_LANGUAGE = "en-IN"


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
	# Try matching just the primary subtag (e.g. "hi" -> "hi-IN").
	primary = code.split("-")[0].lower()
	for supported in LANGUAGES:
		if supported.split("-")[0].lower() == primary:
			return supported
	return DEFAULT_TTS_FALLBACK_LANGUAGE

# Translation output styles accepted by /translate.
TRANSLATE_MODES = ("formal", "modern-colloquial", "classic-colloquial", "code-mixed")
DEFAULT_TRANSLATE_MODE = "formal"

# Speaker gender hint for translation.
SPEAKER_GENDERS = ("Male", "Female")

# Numerals formatting for translate / transliterate.
NUMERALS_FORMATS = ("international", "native")

# Output script options for translate.
OUTPUT_SCRIPTS = ("", "roman", "fully-native", "spoken-form-in-native")

# --- Audio ------------------------------------------------------------------
TTS_SAMPLE_RATES = (8000, 16000, 22050)
DEFAULT_TTS_SAMPLE_RATE = 22050

# Value bounds for the TTS prosody controls, matching the API.
# bulbul:v3 accepts pace 0.5-2.0 and temperature 0-1. It does NOT support
# pitch or loudness (HTTP 400 if sent). See ttsstyles for the enforced ranges.
PACE_RANGE = (0.5, 2.0)
TEMPERATURE_RANGE = (0.05, 1.0)

# Recognised audio extensions for STT input.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif")
# Inputs accepted by Sarvam document OCR: a PDF directly, or an image we wrap
# into a single-page PDF before uploading.
OCR_INPUT_EXTENSIONS = (".pdf",) + IMAGE_EXTENSIONS

# Maximum characters the TTS endpoint accepts per request. Longer input is
# chunked automatically by the client.
TTS_MAX_CHARS = 1500

# Maximum characters sent to /translate per request; longer input is split on
# paragraph/sentence boundaries and re-joined.
TRANSLATE_MAX_CHARS = 1800
