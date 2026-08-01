# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Text-to-speech styles, genders and a filtered voice catalogue.

Sarvam's /text-to-speech takes: speaker (voice), model ("bulbul:v3" latest or
"bulbul:v2"), pace, pitch, loudness, temperature. There is no native
"speaking style" parameter, so a style is applied as a prosody preset
(pace/pitch/loudness/temperature) - an intentional value-add.

The Voice list is filtered by (style, gender): choosing a style and a gender
narrows the voices to a curated set appropriate for that combination, so the
user is never shown a long or incompatible voice list. Voice-to-style grouping
is curated by this add-on (Sarvam does not tag voices by style); gender for
bulbul:v2 follows Sarvam's published female/male split, and for bulbul:v3 it is
assigned by this add-on.
"""

DEFAULT_MODEL = "bulbul:v3"
MODELS = ("bulbul:v3", "bulbul:v2")
GENDERS = ("Female", "Male")

# Ordered (key, human label). These are the "speaking styles" the user picks.
STYLES = (
	("news", "News reader"),
	("conversational", "Conversational"),
	("narration", "Narration"),
	("formal", "Formal"),
	("expressive", "Expressive"),
)

# Prosody presets per style: pace, pitch, loudness, temperature (clamped).
_STYLE_PARAMS = {
	"news": {"pace": 1.05, "pitch": 0.0, "loudness": 1.1, "temperature": 0.3},
	"conversational": {"pace": 1.0, "pitch": 0.0, "loudness": 1.0, "temperature": 0.7},
	"narration": {"pace": 0.92, "pitch": 0.0, "loudness": 1.0, "temperature": 0.5},
	"formal": {"pace": 0.98, "pitch": -0.05, "loudness": 1.05, "temperature": 0.35},
	"expressive": {"pace": 1.08, "pitch": 0.05, "loudness": 1.1, "temperature": 0.85},
}

_ALL_STYLE_KEYS = tuple(k for k, _ in STYLES)


def _v(name, model, gender, styles=None):
	return {"name": name, "model": model, "gender": gender,
		"styles": tuple(styles) if styles else _ALL_STYLE_KEYS}


# Curated voice catalogue. Each voice is offered for a set of styles so that a
# (style, gender) choice yields a short, sensible list.
VOICES = [
	# bulbul:v3 - female
	_v("anushka", "bulbul:v3", "Female", ("news", "formal", "conversational")),
	_v("vidya", "bulbul:v3", "Female", ("narration", "conversational", "expressive")),
	_v("manisha", "bulbul:v3", "Female", ("news", "formal")),
	_v("arya", "bulbul:v3", "Female", ("expressive", "narration", "conversational")),
	_v("priya", "bulbul:v3", "Female", ("conversational", "expressive")),
	_v("neha", "bulbul:v3", "Female", ("news", "formal", "conversational")),
	_v("ritu", "bulbul:v3", "Female", ("narration", "formal")),
	_v("pooja", "bulbul:v3", "Female", ("conversational", "expressive", "narration")),
	# bulbul:v3 - male
	_v("shubh", "bulbul:v3", "Male", ("news", "formal", "conversational")),
	_v("abhilash", "bulbul:v3", "Male", ("news", "formal")),
	_v("karun", "bulbul:v3", "Male", ("narration", "conversational")),
	_v("hitesh", "bulbul:v3", "Male", ("conversational", "expressive")),
	_v("rahul", "bulbul:v3", "Male", ("news", "formal", "conversational")),
	_v("aditya", "bulbul:v3", "Male", ("narration", "expressive")),
	_v("rohan", "bulbul:v3", "Male", ("conversational", "expressive", "narration")),
	_v("vijay", "bulbul:v3", "Male", ("formal", "news")),
	# bulbul:v2 (Sarvam-documented genders)
	_v("anushka", "bulbul:v2", "Female"),
	_v("manisha", "bulbul:v2", "Female"),
	_v("vidya", "bulbul:v2", "Female"),
	_v("arya", "bulbul:v2", "Female"),
	_v("abhilash", "bulbul:v2", "Male"),
	_v("karun", "bulbul:v2", "Male"),
	_v("hitesh", "bulbul:v2", "Male"),
]


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


def style_params(key):
	p = dict(_STYLE_PARAMS.get(key, _STYLE_PARAMS["conversational"]))
	return {
		"pace": _clamp(p["pace"], 0.3, 3.0),
		"pitch": _clamp(p["pitch"], -0.75, 0.75),
		"loudness": _clamp(p["loudness"], 0.1, 3.0),
		"temperature": _clamp(p["temperature"], 0.0, 1.0),
	}


def voices_for(model, gender, style):
	"""Return the curated voice names for a (model, gender, style)."""
	names = []
	for v in VOICES:
		if v["model"] != model:
			continue
		if gender and v["gender"] != gender:
			continue
		if style and style not in v["styles"]:
			continue
		if v["name"] not in names:
			names.append(v["name"])
	if not names:  # fallback: all voices of that gender for the model
		for v in VOICES:
			if v["model"] == model and (not gender or v["gender"] == gender):
				if v["name"] not in names:
					names.append(v["name"])
	return names


def default_voice(model, gender=None, style=None):
	names = voices_for(model, gender or "Female", style or default_style())
	return names[0] if names else "shubh"
