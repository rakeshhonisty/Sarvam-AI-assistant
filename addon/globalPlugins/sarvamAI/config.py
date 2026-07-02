# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Configuration handling built on NVDA's own ``config`` framework.

Settings are persisted in NVDA's ``nvda.ini`` under a ``[sarvamAI]`` section and
loaded automatically on start. The API key is lightly obfuscated on disk (see
:func:`getApiKey`/:func:`setApiKey`) so that it is not stored as clear text in
the configuration file; this is obfuscation, not strong encryption, and is
documented as such.
"""

import base64
import config

from . import constants

SECTION = "sarvamAI"

#: The configuration specification handed to NVDA's config validator.
CONFIG_SPEC = {
	# Stored obfuscated; never read this directly, use getApiKey().
	"apiKeyObfuscated": "string(default=\"\")",
	"baseUrl": "string(default=\"%s\")" % constants.DEFAULT_BASE_URL,

	# Text to speech defaults.
	"ttsModel": "string(default=\"%s\")" % constants.DEFAULT_TTS_MODEL,
	"defaultSpeaker": "string(default=\"%s\")" % constants.DEFAULT_SPEAKER,
	"defaultLanguage": "string(default=\"auto\")",
	"pitch": "float(default=0.0)",
	"pace": "float(default=1.0)",
	"loudness": "float(default=1.0)",
	"ttsTemperature": "float(default=0.6)",
	"ttsStyle": "string(default=\"neutral\")",
	"ttsGender": "string(default=\"Any\")",
	"ttsCodec": "string(default=\"%s\")" % constants.DEFAULT_TTS_CODEC,
	"sampleRate": "integer(default=%d)" % constants.DEFAULT_TTS_SAMPLE_RATE,
	"enablePreprocessing": "boolean(default=True)",
	"autoPlayTts": "boolean(default=True)",

	# Speech to text defaults.
	"sttModel": "string(default=\"%s\")" % constants.DEFAULT_STT_MODEL,
	"sttTranslateModel": "string(default=\"%s\")" % constants.DEFAULT_STT_TRANSLATE_MODEL,
	"sttLanguage": "string(default=\"unknown\")",

	# Translation defaults.
	"translateModel": "string(default=\"%s\")" % constants.DEFAULT_TRANSLATE_MODEL,
	"translateSourceLang": "string(default=\"auto\")",
	"translateTargetLang": "string(default=\"en-IN\")",
	"translateMode": "string(default=\"%s\")" % constants.DEFAULT_TRANSLATE_MODE,

	# Chat / summarisation defaults.
	"chatModel": "string(default=\"%s\")" % constants.DEFAULT_CHAT_MODEL,
	"chatTemperature": "float(default=0.3)",
	"chatMaxTokens": "integer(default=800)",

	# OCR (document digitization) defaults.
	"ocrEngine": "string(default=\"%s\")" % constants.OCR_ENGINE_SARVAM,
	"ocrLanguage": "string(default=\"%s\")" % constants.DEFAULT_OCR_LANGUAGE,
	"ocrOutputFormat": "string(default=\"%s\")" % constants.DEFAULT_OCR_OUTPUT_FORMAT,

	# Folders.
	"outputFolder": "string(default=\"\")",
	"downloadFolder": "string(default=\"\")",

	# Behaviour.
	"streaming": "boolean(default=False)",
	"networkTimeout": "integer(default=60)",
	"maxRetries": "integer(default=2)",
	"proxyUrl": "string(default=\"\")",
	"debugLogging": "boolean(default=False)",
	"checkForUpdates": "boolean(default=True)",
}


def initialize():
	"""Register the configuration spec with NVDA and materialise defaults.

	NVDA resolves spec defaults through its aggregated sections, but the exact
	behaviour of a spec added at runtime has shifted across NVDA releases. To be
	deterministic we also write any missing key with its parsed default, so
	every read below returns a real value regardless of NVDA version.
	"""
	config.conf.spec[SECTION] = CONFIG_SPEC
	_ensureDefaults()


def conf():
	"""Return the live ``[sarvamAI]`` config section."""
	return config.conf[SECTION]


def _defaultFromSpec(spec):
	"""Parse the ``default=`` value out of a configobj spec string."""
	import re
	m = re.search(r"default\s*=\s*(.*?)\s*\)\s*$", spec)
	if not m:
		return None
	raw = m.group(1).strip()
	if spec.startswith("boolean"):
		return raw.lower() == "true"
	if spec.startswith("integer"):
		try:
			return int(raw)
		except ValueError:
			return 0
	if spec.startswith("float"):
		try:
			return float(raw)
		except ValueError:
			return 0.0
	# string
	if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]:
		raw = raw[1:-1]
	return raw


def _ensureDefaults():
	try:
		if SECTION not in config.conf:
			config.conf[SECTION] = {}
		section = config.conf[SECTION]
	except Exception:
		return
	for key, spec in CONFIG_SPEC.items():
		try:
			value = section[key]
		except Exception:
			value = None
		if value is None:
			try:
				section[key] = _defaultFromSpec(spec)
			except Exception:
				pass


# --- API key obfuscation ----------------------------------------------------
# A fixed XOR pad keeps the key from appearing verbatim in nvda.ini. This is a
# deliberate, documented trade-off: NVDA add-ons run in-process with no OS
# keyring guarantee, so we avoid clear text without over-promising security.
_PAD = b"sarvam-ai-assistant-nvda-obfuscation-pad"


def _xor(data, pad):
	return bytes(b ^ pad[i % len(pad)] for i, b in enumerate(data))


def getApiKey():
	"""Return the de-obfuscated API key, or an empty string."""
	raw = conf().get("apiKeyObfuscated", "") or ""
	if not raw:
		return ""
	try:
		blob = base64.b64decode(raw.encode("ascii"))
		return _xor(blob, _PAD).decode("utf-8")
	except Exception:
		return ""


def setApiKey(key):
	"""Store the API key in obfuscated form."""
	key = (key or "").strip()
	if not key:
		conf()["apiKeyObfuscated"] = ""
		return
	blob = _xor(key.encode("utf-8"), _PAD)
	conf()["apiKeyObfuscated"] = base64.b64encode(blob).decode("ascii")


def restoreDefaults():
	"""Reset every add-on setting to its parsed default value."""
	section = conf()
	for key, spec in CONFIG_SPEC.items():
		try:
			section[key] = _defaultFromSpec(spec)
		except Exception:
			pass
