# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""The model catalogue behind the Model Center (model switching).

Every Sarvam service the add-on uses has a list of models here, each with a
short spoken-friendly description and its capabilities. The UI never hard
codes a model name: it asks this module what is available, what a model can do
(see images, call tools, how it reasons) and what the safe default is.

Catalogue verified against the Sarvam documentation on 2026-11-20
(``/v2/chat/completions`` model enum, Bulbul, Saaras and Document AI guides).

Retired by Sarvam and therefore removed from this add-on (an upgraded install
is migrated automatically, see ``config._migrateStaleValues``):

* chat: ``sarvam-m`` (Jun 2026), ``sarvam-30b`` (Aug 2026), ``sarvam-30b-16k``,
  ``sarvam-105b-32k``, ``kimi-k3``, ``mimo-v2.6-flash``, ``mimo-v2.6-pro``
* text to speech: ``bulbul:v2``
* speech to text: ``saarika:*`` and the legacy ``/speech-to-text-translate``
  endpoint with ``saaras:v2.5`` (translation is now ``mode="translate"``)
* OCR: the legacy ``/doc-digitization`` API is replaced by Document AI
  (``/doc-ai/v1``); it is kept only as an automatic fallback.
"""

# --- Chat / reasoning / agent models (POST /v2/chat/completions) ------------
# Fields:
#   id          exact, case-sensitive model id sent to the API
#   label       short name read in combo boxes
#   family      "Sarvam" or the open-model family it comes from
#   context     context window in tokens
#   vision      True when the model accepts image input (image_url parts)
#   efforts     reasoning_effort values the model accepts ("none" = thinking off)
#   effort      the default reasoning effort used by this add-on
#   provisioned True when Sarvam serves it only on Provisioned Throughput
#               (the key's organisation must have it enabled)
#   about       one sentence describing what the model is good at
CHAT_MODELS = (
	dict(id="sarvam-105b", label="Sarvam 105B", family="Sarvam", context=128000,
		vision=False, efforts=("none", "low", "medium", "high"), effort="medium",
		provisioned=False,
		about="Sarvam's own flagship reasoning model, strongest for Indian languages."),
	dict(id="glm5.3-flash", label="GLM 5.3 Flash", family="GLM (open model)",
		context=1048576, vision=True, efforts=("low", "high"), effort="high",
		provisioned=False,
		about="Fast open model with a 1 million token context and image understanding."),
	dict(id="glm5.3", label="GLM 5.3", family="GLM (open model)", context=1048576,
		vision=False, efforts=("low", "high"), effort="high", provisioned=False,
		about="Large open model for long documents and deep multi-step reasoning."),
	dict(id="gemma4", label="Gemma 4 (31B)", family="Gemma (open model)",
		context=262144, vision=True, efforts=("none", "low", "medium", "high"),
		effort="none", provisioned=False,
		about="Google's open Gemma 4 model, quick and good at describing images."),
	dict(id="deepseekv4.1-flash-1017", label="DeepSeek V4.1 Flash",
		family="DeepSeek (open model)", context=1048576, vision=True,
		efforts=("none", "low", "medium", "high"), effort="high", provisioned=False,
		about="Fast, low cost open model with a 1 million token context and vision."),
	dict(id="deepseekv4.1-flash-1017-interactive", label="DeepSeek V4.1 Flash Interactive",
		family="DeepSeek (open model)", context=1048576, vision=True,
		efforts=("none", "low", "medium", "high"), effort="none", provisioned=False,
		about="Low latency variant of DeepSeek V4.1 Flash, tuned for quick replies."),
	dict(id="deepseekv4-pro", label="DeepSeek V4 Pro", family="DeepSeek (open model)",
		context=1000000, vision=False, efforts=("none", "low", "medium", "high"),
		effort="high", provisioned=True,
		about="Most capable DeepSeek model for hard reasoning (Provisioned Throughput only)."),
	dict(id="kimi-k3.1-pro", label="Kimi K3.1 Pro", family="Kimi (open model)",
		context=1048576, vision=True, efforts=("low", "medium", "high", "max"),
		effort="high", provisioned=True,
		about="Always-thinking agentic model (Provisioned Throughput only)."),
	dict(id="qwen38-27b", label="Qwen 3.8 (27B)", family="Qwen (open model)",
		context=262144, vision=False, efforts=("none", "low", "medium", "high"),
		effort="none", provisioned=True,
		about="Compact open model (Provisioned Throughput only)."),
)

DEFAULT_CHAT_MODEL = "sarvam-105b"
# Used automatically when an image is attached and the chosen chat model
# cannot see images.
DEFAULT_VISION_MODEL = "gemma4"

# Chat models Sarvam has retired. Any of these found in an old configuration is
# replaced by DEFAULT_CHAT_MODEL.
RETIRED_CHAT_MODELS = (
	"sarvam-m", "sarvam-30b", "sarvam-30b-16k", "sarvam-105b-32k",
	"kimi-k3", "mimo-v2.6-flash", "mimo-v2.6-pro",
)

# Human labels for the reasoning effort values.
EFFORT_LABELS = {
	"none": "Off (fastest, no thinking)",
	"low": "Low",
	"medium": "Medium",
	"high": "High",
	"max": "Maximum",
}


def chat_ids():
	return tuple(m["id"] for m in CHAT_MODELS)


def chat_info(model_id):
	for m in CHAT_MODELS:
		if m["id"] == model_id:
			return m
	return None


def vision_ids():
	return tuple(m["id"] for m in CHAT_MODELS if m["vision"])


def supports_vision(model_id):
	info = chat_info(model_id)
	return bool(info and info["vision"])


def efforts_for(model_id):
	info = chat_info(model_id)
	return tuple(info["efforts"]) if info else ("low", "medium", "high")


def default_effort(model_id):
	info = chat_info(model_id)
	return info["effort"] if info else "medium"


def normalise_effort(model_id, effort):
	"""Return an effort the model accepts, preferring ``effort``."""
	allowed = efforts_for(model_id)
	if effort in allowed:
		return effort
	return default_effort(model_id) if default_effort(model_id) in allowed else allowed[0]


def chat_label(model_id):
	info = chat_info(model_id)
	if not info:
		return model_id
	label = info["label"]
	if info["provisioned"]:
		label += " - provisioned"
	return label


def describe_chat(model_id):
	"""A sentence or two a screen reader can speak about the model."""
	info = chat_info(model_id)
	if not info:
		return model_id
	parts = [info["about"]]
	parts.append("Family: %s." % info["family"])
	if info["context"] >= 1000000:
		parts.append("Context: about %d million tokens." % round(info["context"] / 1000000.0))
	else:
		parts.append("Context: %d thousand tokens." % (info["context"] // 1000))
	parts.append("Sees images: %s." % ("yes" if info["vision"] else "no"))
	parts.append("Reasoning levels: %s." % ", ".join(
		EFFORT_LABELS.get(e, e) for e in info["efforts"]))
	parts.append("Model id: %s." % info["id"])
	return " ".join(parts)


# --- Text to speech (Bulbul) -----------------------------------------------
TTS_MODELS = (
	dict(id="bulbul:v4-flash", label="Bulbul v4 Flash (newest, 222 persona voices)",
		max_chars=2500,
		languages=("hi-IN", "en-IN", "bn-IN", "gu-IN", "kn-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN"),
		about="Sarvam's newest voice model. Each voice is a persona made for a kind of "
			"work: news, narration, customer support, education, ads, devotional and more."),
	dict(id="bulbul:v3", label="Bulbul v3 (37 voices, all 11 languages)",
		max_chars=2500,
		languages=("hi-IN", "en-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN",
			"od-IN", "pa-IN", "ta-IN", "te-IN"),
		about="The previous generation. Covers Malayalam and Odia, which Bulbul v4 Flash "
			"does not, so the add-on falls back to it automatically for those languages."),
)
DEFAULT_TTS_MODEL = "bulbul:v4-flash"
FALLBACK_TTS_MODEL = "bulbul:v3"
RETIRED_TTS_MODELS = ("bulbul:v1", "bulbul:v2")


def tts_ids():
	return tuple(m["id"] for m in TTS_MODELS)


def tts_info(model_id):
	for m in TTS_MODELS:
		if m["id"] == model_id:
			return m
	return TTS_MODELS[0]


def tts_supports_language(model_id, lang):
	return lang in tts_info(model_id)["languages"]


# --- Speech to text (Saaras) ------------------------------------------------
STT_MODELS = (
	dict(id="saaras:v4", label="Saaras v4 (newest)",
		about="Most accurate. Supports key terms (names and jargon you want spelled "
			"right) and every output mode."),
	dict(id="saaras:v3", label="Saaras v3",
		about="Previous generation, still supported. No key terms."),
)
DEFAULT_STT_MODEL = "saaras:v4"
RETIRED_STT_MODELS = ("saarika:v1", "saarika:v2", "saarika:v2.5", "saaras:v2", "saaras:v2.5")


def stt_ids():
	return tuple(m["id"] for m in STT_MODELS)


def stt_supports_keyterms(model_id):
	return model_id == "saaras:v4"


# --- Translation (Mayura / Sarvam-Translate) --------------------------------
TRANSLATE_MODELS = (
	dict(id="sarvam-translate:v1", label="Sarvam-Translate (22 Indian languages)",
		max_chars=2000,
		about="Long-form translation across all 22 scheduled Indian languages and English."),
	dict(id="mayura:v1", label="Mayura (styles and code-mixing)",
		max_chars=1000,
		about="10 Indian languages and English with formal, colloquial and code-mixed styles."),
)
DEFAULT_TRANSLATE_MODEL = "sarvam-translate:v1"


def translate_ids():
	return tuple(m["id"] for m in TRANSLATE_MODELS)


def translate_info(model_id):
	for m in TRANSLATE_MODELS:
		if m["id"] == model_id:
			return m
	return TRANSLATE_MODELS[0]


# --- Document engine ----------------------------------------------------------
DOC_ENGINES = (
	dict(id="docai", label="Sarvam Document AI (Vision 2.1)",
		about="Current engine. Reads PDFs, PNG and JPEG images and ZIPs of page images, "
			"keeps headings, tables and reading order, and can extract fields to "
			"CSV, Excel or JSON."),
	dict(id="legacy", label="Legacy document digitization",
		about="The older OCR API. Only use it if Document AI is not enabled on your key."),
)
DEFAULT_DOC_ENGINE = "docai"


def doc_engine_ids():
	return tuple(m["id"] for m in DOC_ENGINES)


# --- Generic helpers used by the Model Center ---------------------------------
SERVICES = (
	# key, label, catalogue, default, config key
	("chat", "AI Workforce and Agent (chat model)", CHAT_MODELS, DEFAULT_CHAT_MODEL, "chatModel"),
	("vision", "Image and screen description (vision model)",
		tuple(m for m in CHAT_MODELS if m["vision"]), DEFAULT_VISION_MODEL, "visionModel"),
	("tts", "Text to speech (voice model)", TTS_MODELS, DEFAULT_TTS_MODEL, "ttsModel"),
	("stt", "Speech to text", STT_MODELS, DEFAULT_STT_MODEL, "sttModel"),
	("translate", "Translation", TRANSLATE_MODELS, DEFAULT_TRANSLATE_MODEL, "translateModel"),
	("doc", "Documents and OCR", DOC_ENGINES, DEFAULT_DOC_ENGINE, "docEngine"),
)


def describe(service_key, model_id):
	"""Description of any model for the Model Center."""
	if service_key in ("chat", "vision"):
		return describe_chat(model_id)
	for key, _label, catalogue, _default, _cfg in SERVICES:
		if key == service_key:
			for m in catalogue:
				if m["id"] == model_id:
					return "%s Model id: %s." % (m["about"], m["id"])
	return model_id


def label_of(service_key, model_id):
	if service_key in ("chat", "vision"):
		return chat_label(model_id)
	for key, _label, catalogue, _default, _cfg in SERVICES:
		if key == service_key:
			for m in catalogue:
				if m["id"] == model_id:
					return m["label"]
	return model_id
