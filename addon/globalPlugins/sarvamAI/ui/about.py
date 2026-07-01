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
	return "1.0.0"


def about_text():
	return _(
		"Sarvam AI assistant for NVDA\n"
		"Version: {version}\n\n"
		"An accessible interface to the Sarvam AI platform: text to speech, "
		"speech to text, translation, transliteration, language detection, "
		"AI chat and summarisation, and OCR.\n\n"
		"Enter your Sarvam API key in the Sarvam AI settings to get started. "
		"Get a key from the Sarvam dashboard at https://dashboard.sarvam.ai.\n\n"
		"OCR uses Sarvam Document OCR (23 languages) by default, with an "
		"offline Windows OCR engine also available. Recognised text can be "
		"translated or summarised with Sarvam.\n\n"
		"Licensed under the GNU General Public License version 2."
	).format(version=_version())
