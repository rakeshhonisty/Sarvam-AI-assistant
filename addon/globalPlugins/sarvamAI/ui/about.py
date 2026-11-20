# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""About text for the add-on."""

import addonHandler

from .. import constants

addonHandler.initTranslation()


def _version():
	try:
		for addon in addonHandler.getRunningAddons():
			if addon.name == constants.ADDON_NAME:
				return addon.version
	except Exception:
		pass
	return "2.0"


def about_text():
	return _(
		"Sarvam AI assistant for NVDA\n"
		"Version: {version}\n\n"
		"An accessible interface to the Sarvam AI platform: text to speech with "
		"Bulbul v4 Flash persona voices, speech to text with Saaras v4, "
		"translation of text and whole documents, transliteration, language "
		"detection, Sarvam Document AI, the AI Workforce and the Sarvam Agent, "
		"dubbing of video and audio into Indian languages, AI vision for images "
		"and the screen (NVDA+Alt+A), and model switching between "
		"Sarvam 105B and Sarvam's open models (GLM, Gemma, DeepSeek and more).\n\n"
		"Enter your Sarvam API key in the Sarvam AI settings to get started. "
		"Get a key from the Sarvam dashboard at https://dashboard.sarvam.ai.\n\n"
		"Licensed under the GNU General Public License version 2."
	).format(version=_version())
