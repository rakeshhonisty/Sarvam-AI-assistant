# -*- coding: utf-8 -*-
"""Text-to-speech style presets and speaker data for the Sarvam AI TTS dialog.

This module backs the "text to speech" dialog for Sarvam's ``/text-to-speech``
API. It provides:

* The list of supported models (``bulbul:v3`` latest, ``bulbul:v2``).
* Ground-truth speaker names for each model.
* A set of "style" presets (news, audiobook, etc.).

IMPORTANT: Sarvam's ``/text-to-speech`` endpoint has NO native "style" or
"genre" parameter. The request only accepts ``speaker``, ``model``, ``pace``,
``pitch``, ``loudness`` and ``temperature``. So the "styles" offered here are an
intentional value-add feature: each preset simply maps to a sensible
combination of ``pace`` / ``pitch`` / ``loudness`` / ``temperature`` that the
caller then sends to the API. ``temperature`` only meaningfully affects
``bulbul:v3`` (higher = more expressive/varied), but it is always included in
the preset so the caller can pass it unconditionally.

Design constraints for this file:

* Pure Python, standard library only.
* No NVDA imports, no third-party imports, no ``_()`` gettext helper.
* Must import cleanly on its own (e.g. under a plain CPython interpreter).
"""

# --- Models -----------------------------------------------------------------

# The default model presented in the dialog. "bulbul:v3" is the latest.
DEFAULT_MODEL = "bulbul:v3"

# All models the dialog offers, in preference order.
MODELS = ("bulbul:v3", "bulbul:v2")

# Gender filter choices offered in the dialog. Only meaningful for v2 (see
# below); v3 does not publish per-speaker genders.
GENDERS = ("Any", "Female", "Male")


# --- Speaker data (ground truth; do NOT invent additional speakers) ---------

# bulbul:v3 speakers. Sarvam does not publish per-speaker genders for v3, so
# gender filtering does not apply here -- every v3 speaker is returned for any
# requested gender.
_V3_SPEAKERS = (
    "shubh", "aditya", "ritu", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun",
    "manan", "sumit", "roopa", "kabir", "aayan", "ashutosh", "advait", "anand",
    "tanya", "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani",
    "mohit", "kavitha", "rehan", "soham", "rupali",
)

# bulbul:v2 speakers, split by published gender so gender filtering works.
_V2_FEMALE_SPEAKERS = ("anushka", "manisha", "vidya", "arya")
_V2_MALE_SPEAKERS = ("abhilash", "karun", "hitesh")

# Combined v2 list in a stable order (all female, then all male).
_V2_SPEAKERS = _V2_FEMALE_SPEAKERS + _V2_MALE_SPEAKERS


# --- Style presets ----------------------------------------------------------

# Ordered tuple of (key, human_label) pairs. Order is the display order.
STYLES = (
    ("neutral", "Neutral / default"),
    ("news", "News reading"),
    ("audiobook", "Audiobook / narration"),
    ("entertainment", "Entertainment / expressive"),
    ("conversational", "Conversational"),
    ("storytelling", "Storytelling"),
)

# Raw preset values, before clamping. Each maps a style key to the four tunable
# parameters. These are hand-picked to evoke the named delivery style.
_STYLE_PRESETS = {
    # Balanced baseline -- matches the API defaults.
    "neutral": {"pace": 1.0, "pitch": 0.0, "loudness": 1.0, "temperature": 0.6},
    # Crisp, slightly quicker and louder, low variability for authority.
    "news": {"pace": 1.05, "pitch": 0.0, "loudness": 1.1, "temperature": 0.3},
    # Measured narration, a touch slower, moderate variability.
    "audiobook": {"pace": 0.92, "pitch": 0.0, "loudness": 1.0, "temperature": 0.5},
    # Lively and animated: faster with high variability.
    "entertainment": {"pace": 1.1, "pitch": 0.0, "loudness": 1.05, "temperature": 0.85},
    # Natural chat cadence, slightly relaxed variability.
    "conversational": {"pace": 1.0, "pitch": 0.0, "loudness": 1.0, "temperature": 0.7},
    # Slower, warm and expressive.
    "storytelling": {"pace": 0.9, "pitch": 0.0, "loudness": 1.0, "temperature": 0.8},
}


# --- Parameter ranges & clamping --------------------------------------------

# Safe/hard ranges enforced on every preset value. These mirror the API's
# accepted ranges (pace hard range 0.3..3.0; loudness generous 0.1..3.0;
# pitch kept within a musical +/-0.75; temperature 0..1).
_PACE_MIN, _PACE_MAX = 0.3, 3.0
_PITCH_MIN, _PITCH_MAX = -0.75, 0.75
_LOUDNESS_MIN, _LOUDNESS_MAX = 0.1, 3.0
_TEMPERATURE_MIN, _TEMPERATURE_MAX = 0.0, 1.0


def _clamp(value, low, high):
    """Return ``value`` constrained to the inclusive range [low, high]."""
    return max(low, min(high, value))


# --- Public interface -------------------------------------------------------

def style_keys():
    """Return a tuple of the style keys, in display order."""
    return tuple(key for key, _label in STYLES)


def style_label(key):
    """Return the human-readable label for a style ``key``.

    Falls back to the key itself if it is not a known style.
    """
    for k, label in STYLES:
        if k == key:
            return label
    return str(key)


def default_speaker(model):
    """Return the default speaker for a given ``model``.

    "shubh" for bulbul:v3, "anushka" for bulbul:v2. Unknown models fall back to
    the v3 default.
    """
    if model == "bulbul:v2":
        return "anushka"
    return "shubh"


def speakers_for(model, gender="Any"):
    """Return the list of speakers for ``model``, optionally filtered by gender.

    * For bulbul:v2, the ``gender`` argument ("Any", "Female" or "Male") filters
      the returned speakers, because v2 genders are published.
    * For bulbul:v3 (and any unknown model), ``gender`` is ignored and the full
      speaker list is returned, because v3 per-speaker genders are not
      published.
    """
    if model == "bulbul:v2":
        if gender == "Female":
            return list(_V2_FEMALE_SPEAKERS)
        if gender == "Male":
            return list(_V2_MALE_SPEAKERS)
        return list(_V2_SPEAKERS)
    # v3 (default): always return every speaker regardless of requested gender.
    return list(_V3_SPEAKERS)


def style_params(key):
    """Return the TTS parameters for a style ``key``.

    Returns a dict with ``pace``, ``pitch``, ``loudness`` and ``temperature``,
    all clamped to their safe ranges. Unknown keys fall back to the "neutral"
    preset.
    """
    preset = _STYLE_PRESETS.get(key, _STYLE_PRESETS["neutral"])
    return {
        "pace": _clamp(float(preset["pace"]), _PACE_MIN, _PACE_MAX),
        "pitch": _clamp(float(preset["pitch"]), _PITCH_MIN, _PITCH_MAX),
        "loudness": _clamp(float(preset["loudness"]), _LOUDNESS_MIN, _LOUDNESS_MAX),
        "temperature": _clamp(
            float(preset["temperature"]), _TEMPERATURE_MIN, _TEMPERATURE_MAX
        ),
    }
