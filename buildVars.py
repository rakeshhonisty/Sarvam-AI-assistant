# -*- coding: UTF-8 -*-
# Build variables for the Sarvam AI assistant NVDA add-on.
# Consumed by build.py (and compatible with the community add-on template).

addon_info = {
	# Add-on internal module name (must match the globalPlugins package folder).
	"addon_name": "sarvamAI",
	# Human readable summary shown in NVDA's Add-on Store / manager.
	"addon_summary": "Sarvam AI assistant",
	# Longer description.
	"addon_description": (
		"Accessible NVDA add-on for the Sarvam AI platform. Provides text to "
		"speech, speech to text, translation, transliteration, language "
		"detection, AI chat and summarisation, and OCR (Sarvam Document OCR in "
		"23 languages, plus an offline Windows OCR engine). Fully keyboard "
		"accessible and screen-reader friendly."
	),
	"addon_version": "1.0.0",
	"addon_author": "Sarvam AI assistant contributors <rakesh.honistyboy@gmail.com>",
	"addon_url": "https://github.com/rakeshhonisty/Sarvam-AI-assistant",
	"addon_sourceURL": "https://github.com/rakeshhonisty/Sarvam-AI-assistant",
	"addon_docFileName": "readme.html",
	"addon_minimumNVDAVersion": "2021.1",
	"addon_lastTestedNVDAVersion": "2026.1",
	"addon_updateChannel": None,
	"addon_license": "GPL v2",
	"addon_licenseURL": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
}

# Files/directories, relative to the addon/ folder, that make up the package.
addon_package_dirs = ["globalPlugins", "doc", "locale"]

# Python source that should be scanned when generating the translation template.
i18nSources = ["addon/globalPlugins"]
