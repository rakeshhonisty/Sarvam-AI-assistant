# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Voice catalogue and voice classification for every Bulbul model.

Version 2.0 keeps the add-on's voice classification (gender + nature of work /
purpose) and extends it to the new **bulbul:v4-flash** persona voices, so the
same three questions pick a voice on either model:

1. **Gender** - Female or Male.
2. **Purpose** - the nature of the work (news, narration, customer support,
   education, ads and social media, devotional, ...).
3. **Language** - v4-flash personas are recorded per language (Hindi, English,
   Hinglish, Marathi, Kannada, ...); v3 voices speak every language.

How each model is classified
----------------------------
* **bulbul:v4-flash** voice ids encode the persona: ``<name>_<lang>_<purpose>``,
  for example ``ritu_hi_banking`` or ``shubh_en_audiobook``. The language and
  purpose come straight from the id (see :data:`PURPOSE_TAGS`); Sarvam's own
  recommendation tables were used to confirm genders where they exist.
* **bulbul:v3** voices have no persona in their name, so they keep the
  hand-made style grouping from 1.x (:data:`_V3_VOICES`).

Sarvam does not publish a gender field for any voice. Genders here are
assigned by this add-on from the voice names (and Sarvam's "recommended male /
female" tables). It only affects filtering - any voice can still be chosen.

Both v3 and v4-flash accept only ``pace`` (0.5 - 2.0) and ``temperature``
(0.01 - 1.0); ``pitch`` and ``loudness`` are rejected with HTTP 400, so they are
never sent. A purpose therefore maps to a pace + temperature preset.
"""

MODEL_V4 = "bulbul:v4-flash"
MODEL_V3 = "bulbul:v3"
MODEL = MODEL_V4
DEFAULT_MODEL = MODEL_V4
MODELS = (MODEL_V4, MODEL_V3)
GENDERS = ("Female", "Male")

# API-enforced ranges for bulbul:v3 and v4-flash.
PACE_MIN, PACE_MAX = 0.5, 2.0
TEMPERATURE_MIN, TEMPERATURE_MAX = 0.05, 1.0

# --- Purposes (nature of work) ------------------------------------------------
# Ordered (key, human label). One list for both models so the user's choice
# carries across a model switch.
PURPOSES = (
	("conversational", "Conversational - natural, everyday speech"),
	("narration", "Narration, stories and audiobooks"),
	("news", "News and documentary"),
	("customer", "Customer support, banking and business"),
	("education", "Education and children"),
	("ads", "Ads, sales and social media"),
	("devotional", "Devotional and spiritual"),
	("drama", "Drama, suspense and characters"),
	("companion", "Companion and personal assistant"),
	("sports", "Sports commentary"),
	("numbers", "Numbers, data and announcements"),
	("formal", "Formal and official text"),
	("expressive", "Expressive - most lively and emotional"),
)
PURPOSE_KEYS = tuple(k for k, _ in PURPOSES)

# Backward-compatible names used by 1.x code and saved settings.
STYLES = PURPOSES

# Prosody preset per purpose (only pace and temperature exist on v3/v4).
# "temperature" is the expression control: low values sound flat, high values
# sound varied and lively.
_PURPOSE_PARAMS = {
	"conversational": {"pace": 1.0, "temperature": 0.8},
	"narration": {"pace": 0.95, "temperature": 0.75},
	"news": {"pace": 1.05, "temperature": 0.55},
	"customer": {"pace": 1.0, "temperature": 0.6},
	"education": {"pace": 0.95, "temperature": 0.7},
	"ads": {"pace": 1.1, "temperature": 0.9},
	"devotional": {"pace": 0.9, "temperature": 0.65},
	"drama": {"pace": 1.0, "temperature": 0.95},
	"companion": {"pace": 1.0, "temperature": 0.8},
	"sports": {"pace": 1.15, "temperature": 0.95},
	"numbers": {"pace": 0.95, "temperature": 0.45},
	"formal": {"pace": 0.95, "temperature": 0.5},
	"expressive": {"pace": 1.05, "temperature": 0.95},
}

# v4-flash persona tags (the part after the language in a voice id) and the
# purpose each belongs to. Unknown tags fall back to "conversational".
PURPOSE_TAGS = {
	"conversational": "conversational", "conversation": "conversational",
	"narration": "narration", "narration_gentle": "narration",
	"stories": "narration", "stories_mixed": "narration", "audiobook": "narration",
	"stories_dramatic": "drama",
	"news": "news", "news_breaking": "news", "documentary": "news",
	"customer": "customer", "customer_utility": "customer",
	"customer_warm": "customer", "customer_expressive": "customer",
	"banking": "customer", "banking_expressive": "customer",
	"insurance": "customer", "kyc": "customer", "recovery": "customer",
	"feedback": "customer", "ecomm": "customer", "market": "customer",
	"medical": "customer", "automobile": "customer", "interview": "customer",
	"edtech": "education", "edtech_bot": "education", "kids": "education",
	"ads": "ads", "ads_formal": "ads", "ads_informal": "ads", "sales": "ads",
	"reels": "ads", "social": "ads", "social_lively": "ads",
	"social_energetic": "ads", "social_excited": "ads",
	"devotional": "devotional",
	"character": "drama", "suspense": "drama", "romantic": "drama",
	"latenight": "drama", "latenight_warm": "drama",
	"companion": "companion", "assistant": "companion", "therapist": "companion",
	"sports": "sports", "sports_energetic": "sports",
	"numbers": "numbers",
}

# Tags that describe how something is said rather than what it is for. A voice
# carrying one is also listed under "expressive".
_EXPRESSIVE_TAGS = (
	"customer_expressive", "banking_expressive", "social_lively",
	"social_energetic", "social_excited", "stories_dramatic", "news_breaking",
	"sports_energetic", "ads_informal",
)
# Tags also suited to formal / official reading.
_FORMAL_TAGS = ("ads_formal", "banking", "insurance", "kyc", "documentary", "news", "medical")

# Language tag in a v4-flash id -> the languages it can be used for.
V4_LANGUAGE_TAGS = {
	"hi": ("hi-IN",),
	"en": ("en-IN",),
	"enhi": ("hi-IN", "en-IN"),
	"mr": ("mr-IN",),
	"kn": ("kn-IN",),
	"pa": ("pa-IN",),
	"ta": ("ta-IN",),
	"te": ("te-IN",),
	"gu": ("gu-IN",),
	"bn": ("bn-IN",),
}
V4_LANGUAGE_LABELS = {
	"hi": "Hindi", "en": "English", "enhi": "Hinglish", "mr": "Marathi",
	"kn": "Kannada", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu",
	"gu": "Gujarati", "bn": "Bengali",
}

# Gender of every speaker name used by either model. Assigned by this add-on
# (Sarvam publishes none); confirmed against Sarvam's "recommended male /
# female" tables where a name appears there.
NAME_GENDER = {
	# Female
	"aarti": "Female", "aditi": "Female", "amelia": "Female", "aparna": "Female",
	"chaitra": "Female", "chandrika": "Female", "chhavi": "Female",
	"harpreet": "Female", "ishita": "Female", "kavitha": "Female", "kavya": "Female",
	"mrunal": "Female", "neha": "Female", "nupur": "Female", "payal": "Female",
	"pooja": "Female", "priya": "Female", "ritu": "Female", "roopa": "Female",
	"rupali": "Female", "sanchita": "Female", "sarika": "Female", "shabana": "Female",
	"shalini": "Female", "shilpa": "Female", "shreya": "Female", "shruti": "Female",
	"simran": "Female", "sophia": "Female", "suchitra": "Female", "suhani": "Female",
	"suman": "Female", "tanya": "Female", "vandana": "Female", "zarina": "Female",
	# Male
	"aayan": "Male", "aditya": "Male", "advait": "Male", "amit": "Male",
	"anand": "Male", "aravind": "Male", "arnab": "Male", "aryaman": "Male",
	"ashok": "Male", "ashutosh": "Male", "ashwin": "Male", "bhavik": "Male",
	"bimal": "Male", "chetan": "Male", "chirag": "Male", "dev": "Male",
	"deven": "Male", "girish": "Male", "gokul": "Male", "jaspal": "Male",
	"kabir": "Male", "kalpit": "Male", "kunal": "Male", "mahesh": "Male",
	"manan": "Male", "mani": "Male", "mohit": "Male", "mukul": "Male",
	"nachiket": "Male", "nilesh": "Male", "ojas": "Male", "rahul": "Male",
	"ratan": "Male", "rehan": "Male", "rohan": "Male", "rustom": "Male",
	"sarang": "Male", "shubh": "Male", "soham": "Male", "sumit": "Male",
	"sunny": "Male", "tarun": "Male", "vaibhav": "Male", "varun": "Male",
	"vijay": "Male", "vipul": "Male",
}

# --- bulbul:v4-flash persona voices (222, from Sarvam's Voices page) ---------
V4_VOICE_IDS = (
	# Hindi (116)
	"aayan_hi_conversational", "amit_hi_conversational", "ashutosh_hi_conversational",
	"kabir_hi_conversational", "kavya_hi_conversational", "manan_hi_conversational",
	"rahul_hi_conversational", "sumit_hi_conversational", "aditya_hi_conversational",
	"aditya_hi_sales", "anand_hi_documentary", "anand_hi_news", "aparna_hi_customer",
	"aparna_hi_kyc", "ashok_hi_character", "ashok_hi_news", "chhavi_hi_kids",
	"ishita_hi_ads", "ishita_hi_edtech", "ishita_hi_banking", "ishita_hi_ads_informal",
	"ishita_hi_devotional", "ishita_hi_numbers", "ishita_hi_social", "kunal_hi_kids",
	"mahesh_hi_documentary", "mani_hi_devotional", "mani_hi_conversational",
	"mohit_hi_conversational", "nachiket_hi_devotional", "priya_hi_recovery",
	"ratan_hi_latenight", "ratan_hi_customer_expressive", "ratan_hi_documentary",
	"ratan_hi_devotional", "ratan_hi_recovery", "ratan_hi_social", "ratan_hi_sports",
	"ratan_hi_latenight_warm", "rehan_hi_social", "ritu_hi_customer_utility",
	"ritu_hi_kids", "ritu_hi_conversation", "ritu_hi_customer", "ritu_hi_edtech",
	"ritu_hi_ads_formal", "ritu_hi_banking", "ritu_hi_ads_informal", "ritu_hi_insurance",
	"ritu_hi_edtech_bot", "ritu_hi_medical", "ritu_hi_sales", "ritu_hi_reels",
	"ritu_hi_social", "ritu_hi_customer_warm", "ritu_hi_social_lively",
	"roopa_hi_companion", "roopa_hi_narration", "roopa_hi_recovery", "roopa_hi_market",
	"roopa_hi_conversational", "sanchita_hi_assistant", "sanchita_hi_edtech",
	"sanchita_hi_banking", "sanchita_hi_feedback", "sanchita_hi_ads_formal",
	"sanchita_hi_ads_informal", "sanchita_hi_interview", "sanchita_hi_romantic",
	"sanchita_hi_market", "sanchita_hi_social", "sanchita_hi_kyc",
	"sarika_hi_conversation", "shalini_hi_companion", "shalini_hi_social",
	"shreya_hi_conversational", "shreya_hi_news", "shruti_hi_edtech",
	"shubh_hi_customer", "shubh_hi_ecomm", "shubh_hi_stories_mixed",
	"shubh_hi_devotional", "shubh_hi_ads", "shubh_hi_recovery",
	"shubh_hi_stories_dramatic", "simran_hi_assistant", "simran_hi_narration",
	"simran_hi_automobile", "simran_hi_conversation", "simran_hi_news_breaking",
	"simran_hi_social_energetic", "simran_hi_social_excited", "simran_hi_latenight",
	"simran_hi_news", "simran_hi_recovery", "simran_hi_sales", "suchitra_hi_ecomm",
	"suhani_hi_social", "sunny_hi_ads", "sunny_hi_reels", "tarun_hi_conversational",
	"tarun_hi_sales", "chaitra_hi_customer", "shilpa_hi_narration", "tanya_hi_narration",
	"aarti_hi_customer", "advait_hi_character", "aryaman_hi_ads", "chirag_hi_social",
	"girish_hi_devotional", "mukul_hi_ads", "mukul_hi_suspense", "suman_hi_companion",
	"vaibhav_hi_social", "vandana_hi_ecomm", "vipul_hi_social",
	# English (62)
	"aditi_en_stories", "aparna_en_companion", "aparna_en_edtech", "ashwin_en_sports",
	"ashwin_en_sports_energetic", "chandrika_en_stories", "dev_en_recovery",
	"dev_en_conversational", "deven_en_conversation", "ishita_en_customer",
	"ishita_en_medical", "ishita_en_numbers", "ishita_en_social", "ishita_en_stories",
	"kalpit_en_edtech", "nachiket_en_ads", "neha_en_customer", "neha_en_latenight",
	"nupur_en_kids", "ojas_en_social", "ritu_en_edtech", "ritu_en_latenight",
	"ritu_en_medical", "ritu_en_reels", "rohan_en_recovery", "roopa_en_conversational",
	"rustom_en_suspense", "sanchita_en_companion", "sanchita_en_insurance",
	"sanchita_en_recovery", "sanchita_en_market", "sanchita_en_social",
	"shabana_en_edtech", "shalini_en_companion", "shalini_en_customer",
	"shubh_en_narration", "shubh_en_numbers", "shubh_en_ads", "shubh_en_recovery",
	"shubh_en_audiobook", "shubh_en_narration_gentle", "shubh_en_sports",
	"simran_en_narration", "simran_en_automobile", "simran_en_conversation",
	"simran_en_customer", "simran_en_edtech", "simran_en_edtech_bot", "simran_en_sales",
	"simran_en_recovery", "simran_en_ads", "simran_en_therapist", "sunny_en_social",
	"varun_en_ads", "varun_en_suspense", "zarina_en_conversation",
	"amelia_en_conversational", "sophia_en_conversational", "girish_en_documentary",
	"girish_en_devotional", "payal_en_edtech", "sarang_en_narration",
	# Hinglish (13)
	"ishita_enhi_companion", "ishita_enhi_customer", "ishita_enhi_customer_expressive",
	"sanchita_enhi_companion", "shalini_enhi_companion", "shalini_enhi_customer",
	"shubh_enhi_companion", "shubh_enhi_ads", "shubh_enhi_banking",
	"simran_enhi_companion", "simran_enhi_customer", "simran_enhi_banking_expressive",
	"sunny_enhi_customer",
	# Marathi (9)
	"ishita_mr_conversational", "mrunal_mr_narration", "neha_mr_narration",
	"nilesh_mr_conversation", "ritu_mr_insurance", "ritu_mr_narration",
	"rupali_mr_stories", "soham_mr_narration", "mukul_mr_stories",
	# Kannada (4)
	"chaitra_kn_conversation", "chaitra_kn_narration", "chetan_kn_conversation",
	"suchitra_kn_narration",
	# Punjabi (4)
	"anand_pa_conversation", "anand_pa_customer", "harpreet_pa_narration",
	"jaspal_pa_banking",
	# Tamil (4)
	"aravind_ta_ads", "aravind_ta_suspense", "gokul_ta_narration", "vijay_ta_narration",
	# Telugu (4)
	"kavitha_te_conversation", "kavitha_te_narration", "pooja_te_conversation",
	"tarun_te_narration",
	# Gujarati (3)
	"bhavik_gu_conversation", "pooja_gu_conversational", "pooja_gu_customer",
	# Bengali (3)
	"arnab_bn_conversation", "roopa_bn_conversational", "bimal_bn_suspense",
)
V4_DEFAULT_SPEAKER = "shubh_enhi_ads"

# --- bulbul:v3 voices (37, verified live in 1.0.5) ----------------------------
# (name, styles this voice is offered for). Gender comes from NAME_GENDER.
_V3_VOICES = (
	("ritu", ("news", "formal", "narration", "customer")),
	("priya", ("conversational", "expressive", "companion")),
	("neha", ("news", "formal", "conversational", "customer")),
	("pooja", ("narration", "conversational", "expressive")),
	("simran", ("conversational", "expressive", "ads")),
	("kavya", ("narration", "expressive", "education")),
	("ishita", ("news", "formal", "customer", "numbers")),
	("shreya", ("conversational", "narration", "education")),
	("roopa", ("formal", "narration", "devotional")),
	("tanya", ("conversational", "expressive", "ads")),
	("shruti", ("news", "formal", "education")),
	("suhani", ("expressive", "conversational", "ads")),
	("kavitha", ("narration", "formal", "devotional")),
	("rupali", ("conversational", "narration", "news")),
	("shubh", ("news", "formal", "conversational", "customer")),
	("aditya", ("narration", "expressive", "ads")),
	("rahul", ("news", "formal", "conversational", "customer")),
	("rohan", ("conversational", "expressive", "narration")),
	("amit", ("news", "formal", "numbers")),
	("dev", ("conversational", "narration", "companion")),
	("ratan", ("formal", "narration", "devotional")),
	("varun", ("drama", "expressive", "conversational")),
	("manan", ("conversational", "expressive", "sports")),
	("sumit", ("news", "formal", "sports")),
	("kabir", ("narration", "expressive", "drama")),
	("aayan", ("conversational", "expressive", "ads")),
	("ashutosh", ("news", "formal", "customer")),
	("advait", ("narration", "formal", "drama")),
	("anand", ("narration", "conversational", "news")),
	("tarun", ("news", "conversational", "education")),
	("sunny", ("expressive", "conversational", "ads")),
	("mani", ("formal", "narration", "devotional")),
	("gokul", ("narration", "formal", "devotional")),
	("vijay", ("news", "formal", "sports")),
	("mohit", ("conversational", "expressive", "companion")),
	("rehan", ("expressive", "conversational", "drama")),
	("soham", ("narration", "formal", "education")),
)
V3_SPEAKERS = tuple(v[0] for v in _V3_VOICES)
V3_DEFAULT_SPEAKER = "shubh"

#: Every valid speaker on any supported model.
ALL_SPEAKERS = V3_SPEAKERS + V4_VOICE_IDS
DEFAULT_SPEAKER = V3_DEFAULT_SPEAKER


# --- parsing / classification -------------------------------------------------
def parse_v4(voice_id):
	"""Split ``ritu_hi_customer_warm`` into ``("ritu", "hi", "customer_warm")``."""
	parts = voice_id.split("_")
	if len(parts) < 3:
		return voice_id, "", ""
	return parts[0], parts[1], "_".join(parts[2:])


def gender_of(voice_id):
	name = voice_id.split("_")[0]
	return NAME_GENDER.get(name)


def purposes_of(voice_id):
	"""Every purpose a voice is offered for."""
	if "_" not in voice_id:
		for n, styles in _V3_VOICES:
			if n == voice_id:
				return tuple(styles)
		return ("conversational",)
	_name, _lang, tag = parse_v4(voice_id)
	result = [PURPOSE_TAGS.get(tag, "conversational")]
	if tag in _EXPRESSIVE_TAGS and "expressive" not in result:
		result.append("expressive")
	if tag in _FORMAL_TAGS and "formal" not in result:
		result.append("formal")
	return tuple(result)


def languages_of(voice_id):
	"""Languages a voice is recorded for (v3 voices speak every language)."""
	if "_" not in voice_id:
		return None
	_name, lang, _tag = parse_v4(voice_id)
	return V4_LANGUAGE_TAGS.get(lang, ())


def model_of(voice_id):
	return MODEL_V4 if "_" in voice_id else MODEL_V3


def voice_label(voice_id):
	"""A label a screen reader reads well, e.g.
	"Ritu - Hindi - Customer warm (female)"."""
	if "_" not in voice_id:
		g = gender_of(voice_id)
		return "%s (%s)" % (voice_id.capitalize(), (g or "").lower()) if g else voice_id.capitalize()
	name, lang, tag = parse_v4(voice_id)
	g = gender_of(voice_id)
	text = "%s - %s - %s" % (
		name.capitalize(), V4_LANGUAGE_LABELS.get(lang, lang), tag.replace("_", " ").capitalize())
	return "%s (%s)" % (text, g.lower()) if g else text


def speakers_for_model(model):
	return V4_VOICE_IDS if model == MODEL_V4 else V3_SPEAKERS


def voices_for(gender=None, style=None, model=None, language=None):
	"""Voices for a model matching gender, purpose and language.

	Falls back progressively so the list is never empty: all filters, then
	without the purpose, then without the gender, then every voice of the model.
	``language`` of None or "auto" does not filter.
	"""
	model = model or MODEL_V3
	pool = speakers_for_model(model)
	lang = None if language in (None, "", "auto", "unknown") else language

	def match(v, use_gender, use_purpose):
		if use_gender and gender and gender_of(v) != gender:
			return False
		if use_purpose and style and style not in purposes_of(v):
			return False
		if lang and model == MODEL_V4 and lang not in (languages_of(v) or ()):
			return False
		return True

	for use_gender, use_purpose in ((True, True), (True, False), (False, True), (False, False)):
		names = [v for v in pool if match(v, use_gender, use_purpose)]
		if names:
			return names
	return list(pool)


def purposes_available(model, gender=None, language=None):
	"""Purposes that have at least one voice for this model/gender/language,
	as ``[(key, label, count)]`` in catalogue order."""
	pool = speakers_for_model(model)
	lang = None if language in (None, "", "auto", "unknown") else language
	out = []
	for key, label in PURPOSES:
		n = 0
		for v in pool:
			if gender and gender_of(v) != gender:
				continue
			if lang and model == MODEL_V4 and lang not in (languages_of(v) or ()):
				continue
			if key in purposes_of(v):
				n += 1
		if n:
			out.append((key, label, n))
	return out


def best_v3_voice(gender=None, style=None):
	"""Closest bulbul:v3 voice, used when falling back from v4-flash."""
	names = voices_for(gender, style, model=MODEL_V3)
	return V3_DEFAULT_SPEAKER if V3_DEFAULT_SPEAKER in names else names[0]


# --- prosody --------------------------------------------------------------------
def style_keys():
	return PURPOSE_KEYS


def style_label(key):
	for k, label in PURPOSES:
		if k == key:
			return label
	return key


def default_style():
	return PURPOSES[0][0]


def _clamp(v, lo, hi):
	return max(lo, min(hi, v))


def clamp_pace(v):
	return _clamp(float(v), PACE_MIN, PACE_MAX)


def clamp_temperature(v):
	return _clamp(float(v), TEMPERATURE_MIN, TEMPERATURE_MAX)


def style_params(key):
	# "storytelling" etc. from very old configs map onto narration.
	p = dict(_PURPOSE_PARAMS.get(key) or _PURPOSE_PARAMS["conversational"])
	return {"pace": clamp_pace(p["pace"]), "temperature": clamp_temperature(p["temperature"])}


def default_voice(gender=None, style=None, model=None, language=None):
	model = model or MODEL_V3
	names = voices_for(gender or "Male", style or default_style(), model=model, language=language)
	pref = V4_DEFAULT_SPEAKER if model == MODEL_V4 else V3_DEFAULT_SPEAKER
	return pref if pref in names else (names[0] if names else pref)


def is_valid_speaker(name, model=None):
	if model:
		return name in speakers_for_model(model)
	return name in ALL_SPEAKERS
