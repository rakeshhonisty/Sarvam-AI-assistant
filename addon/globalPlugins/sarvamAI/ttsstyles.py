# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Speaking styles, genders and the bulbul:v3 voice catalogue.

Only **bulbul:v3** is supported. bulbul:v2 is being deprecated by Sarvam and has
been removed from this add-on.

Verified live against the Sarvam API on 2026-08-07:

* bulbul:v3 supports ``pace`` (0.5 - 2.0) and ``temperature`` (0 - 1).
* bulbul:v3 does **NOT** support ``pitch`` or ``loudness``. Sending either
  returns HTTP 400 ("Pitch and loudness parameters are currently not supported
  for the Bulbul V3 model"), which previously made every v3 request fail. Those
  two parameters are therefore never sent, and the dialog offers Speed and
  Expression sliders instead of Pitch and Volume.
* The 37 speaker names below were each verified live against the API. (The
  API's own error message also lists "niharika", but that voice is rejected as
  "not recognized" when actually used, so it is excluded.)

Sarvam does not publish a gender for each v3 voice, so the Female/Male grouping
here is assigned by this add-on from the voice names. It only affects filtering
in the UI - any voice can be selected by switching gender.

A "speaking style" is not a Sarvam parameter; it is applied as a prosody preset
(pace + temperature) and is used to offer a short, relevant voice list.
"""

MODEL = "bulbul:v3"
DEFAULT_MODEL = MODEL
MODELS = (MODEL,)
GENDERS = ("Female", "Male")

# API-enforced ranges for bulbul:v3.
PACE_MIN, PACE_MAX = 0.5, 2.0
TEMPERATURE_MIN, TEMPERATURE_MAX = 0.05, 1.0

# Ordered (key, human label). The labels describe how each style sounds, so the
# effect of the choice is clear from the name alone.
STYLES = (
	("conversational", "Conversational - natural, everyday speech"),
	("narration", "Narration - warm storytelling, for books and articles"),
	("expressive", "Expressive - most lively and emotional"),
	("news", "News reader - crisp and steady, less emotion"),
	("formal", "Formal - measured and neutral, for official text"),
)

# Prosody presets per style (only pace and temperature exist on v3).
# "temperature" is the expression control: low values sound flat and
# monotonous, high values sound varied and lively. Values were raised after
# user feedback that the previous presets sounded too monotonous.
_STYLE_PARAMS = {
	"conversational": {"pace": 1.0, "temperature": 0.8},
	"narration": {"pace": 0.95, "temperature": 0.75},
	"expressive": {"pace": 1.05, "temperature": 0.95},
	"news": {"pace": 1.05, "temperature": 0.55},
	"formal": {"pace": 0.95, "temperature": 0.5},
}

_ALL_STYLES = tuple(k for k, _ in STYLES)

# --- bulbul:v3 voice catalogue (38 voices, as reported by the API) ----------
# (name, gender, styles this voice is offered for)
_VOICES = (
	# Female
	("ritu", "Female", ("news", "formal", "narration")),
	("priya", "Female", ("conversational", "expressive")),
	("neha", "Female", ("news", "formal", "conversational")),
	("pooja", "Female", ("narration", "conversational", "expressive")),
	("simran", "Female", ("conversational", "expressive")),
	("kavya", "Female", ("narration", "expressive")),
	("ishita", "Female", ("news", "formal")),
	("shreya", "Female", ("conversational", "narration")),
	("roopa", "Female", ("formal", "narration")),
	("tanya", "Female", ("conversational", "expressive")),
	("shruti", "Female", ("news", "formal")),
	("suhani", "Female", ("expressive", "conversational")),
	("kavitha", "Female", ("narration", "formal")),
	("rupali", "Female", ("conversational", "narration", "news")),
	# Male
	("shubh", "Male", ("news", "formal", "conversational")),
	("aditya", "Male", ("narration", "expressive")),
	("rahul", "Male", ("news", "formal", "conversational")),
	("rohan", "Male", ("conversational", "expressive", "narration")),
	("amit", "Male", ("news", "formal")),
	("dev", "Male", ("conversational", "narration")),
	("ratan", "Male", ("formal", "narration")),
	("varun", "Male", ("news", "conversational")),
	("manan", "Male", ("conversational", "expressive")),
	("sumit", "Male", ("news", "formal")),
	("kabir", "Male", ("narration", "expressive")),
	("aayan", "Male", ("conversational", "expressive")),
	("ashutosh", "Male", ("news", "formal")),
	("advait", "Male", ("narration", "formal")),
	("anand", "Male", ("narration", "conversational")),
	("tarun", "Male", ("news", "conversational")),
	("sunny", "Male", ("expressive", "conversational")),
	("mani", "Male", ("formal", "narration")),
	("gokul", "Male", ("narration", "formal")),
	("vijay", "Male", ("news", "formal")),
	("mohit", "Male", ("conversational", "expressive")),
	("rehan", "Male", ("expressive", "conversational")),
	("soham", "Male", ("narration", "formal")),
)

#: Every valid bulbul:v3 speaker name.
ALL_SPEAKERS = tuple(v[0] for v in _VOICES)

DEFAULT_SPEAKER = "shubh"


def style_keys():
	return tuple(k for k, _ in STYLES)


def style_label(key):
	for k, label in STYLES:
		if k == key:
			return label
	return key


def default_style():
	return STYLES[0][0]


def _clamp(v, lo, hi):
	return max(lo, min(hi, v))


def clamp_pace(v):
	return _clamp(float(v), PACE_MIN, PACE_MAX)


def clamp_temperature(v):
	return _clamp(float(v), TEMPERATURE_MIN, TEMPERATURE_MAX)


def style_params(key):
	p = dict(_STYLE_PARAMS.get(key, _STYLE_PARAMS["conversational"]))
	return {"pace": clamp_pace(p["pace"]), "temperature": clamp_temperature(p["temperature"])}


def voices_for(gender=None, style=None):
	"""Voices matching a gender and speaking style.

	Falls back progressively so the list is never empty: style filter first,
	then gender only, then every voice.
	"""
	names = [n for n, g, st in _VOICES
		if (not gender or g == gender) and (not style or style in st)]
	if not names and gender:
		names = [n for n, g, _st in _VOICES if g == gender]
	return names or list(ALL_SPEAKERS)


def gender_of(name):
	for n, g, _st in _VOICES:
		if n == name:
			return g
	return None


def default_voice(gender=None, style=None):
	names = voices_for(gender or "Male", style or default_style())
	return DEFAULT_SPEAKER if DEFAULT_SPEAKER in names else (names[0] if names else DEFAULT_SPEAKER)


def is_valid_speaker(name):
	return name in ALL_SPEAKERS
