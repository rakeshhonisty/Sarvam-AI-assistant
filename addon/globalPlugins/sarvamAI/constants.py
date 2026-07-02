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
EP_STT_TRANSLATE_JOB = "/speech-to-text-translate/job/v1"

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
DEFAULT_OCR_LANGUAGE = "en-IN"

# OCR engines exposed in the UI.
OCR_ENGINE_SARVAM = "sarvam"
OCR_ENGINE_WINDOWS = "windows"

# --- Models -----------------------------------------------------------------
TTS_MODELS = ("bulbul:v3", "bulbul:v2")

# Output audio codecs accepted by /text-to-speech (verified from OpenAPI spec).
# "wav" is used for in-app playback; "mp3" for saving a compact file.
TTS_OUTPUT_CODECS = ("mp3", "wav", "opus", "flac", "aac")
DEFAULT_TTS_CODEC = "mp3"
STT_MODELS = ("saarika:v2.5", "saarika:v2", "saarika:v1", "saarika:flash")
STT_TRANSLATE_MODELS = ("saaras:v2.5", "saaras:v2", "saaras:v1", "saaras:flash")
TRANSLATE_MODELS = ("sarvam-translate:v1", "mayura:v1")
# Chat models as returned live by GET /v1/models.
CHAT_MODELS = ("sarvam-105b", "sarvam-30b")

DEFAULT_TTS_MODEL = "bulbul:v3"
DEFAULT_STT_MODEL = "saarika:v2.5"
DEFAULT_STT_TRANSLATE_MODEL = "saaras:v2.5"
DEFAULT_TRANSLATE_MODEL = "sarvam-translate:v1"
DEFAULT_CHAT_MODEL = "sarvam-105b"

# --- Speakers ---------------------------------------------------------------
# bulbul:v2 speakers (default set).
SPEAKERS_V2 = (
	"anushka", "manisha", "vidya", "arya",
	"abhilash", "karun", "hitesh",
)
# bulbul:v1 speakers (kept for compatibility if the user selects v1).
SPEAKERS_V1 = (
	"meera", "pavithra", "maitreyi", "arvind", "amol", "amartya",
	"diya", "neel", "misha", "vian", "arjun", "maya",
)
DEFAULT_SPEAKER = "shubh"


def speakers_for_model(model):
	"""Return the tuple of speaker names appropriate for a TTS model."""
	if model and model.startswith("bulbul:v1"):
		return SPEAKERS_V1
	return SPEAKERS_V2


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
PITCH_RANGE = (-0.75, 0.75)
PACE_RANGE = (0.3, 3.0)
LOUDNESS_RANGE = (0.1, 3.0)

# Recognised audio extensions for STT input.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif")
# Inputs accepted by Sarvam document OCR: a PDF directly, or an image we wrap
# into a single-page PDF before uploading.
OCR_INPUT_EXTENSIONS = (".pdf",) + IMAGE_EXTENSIONS

# Maximum characters the TTS endpoint accepts per request. Longer input is
# chunked automatically by the client.
TTS_MAX_CHARS = 1500
