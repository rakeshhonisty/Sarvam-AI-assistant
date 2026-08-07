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
		"Accessible NVDA add-on for the Sarvam AI platform, built for blind and "
		"visually-impaired users. Text to speech (with document upload and MP3 "
		"export), speech to text including large audio files, translation, "
		"transliteration, language detection, an AI Workforce reasoning layer "
		"(Sarvam-105B), and OCR powered by Sarvam Document Intelligence in 23 "
		"languages that preserves headings, tables and multi-column layout. "
		"Results save as TXT, Word or Markdown. Fully keyboard accessible."
	),
	"addon_version": "1.0.6",
	"addon_author": "Sarvam AI assistant contributors <rakesh.honistyboy@gmail.com>",
	"addon_url": "https://github.com/rakeshhonisty/Sarvam-AI-assistant",
	"addon_sourceURL": "https://github.com/rakeshhonisty/Sarvam-AI-assistant",
	"addon_docFileName": "readme.html",
	"addon_minimumNVDAVersion": "2021.1",
	# Must be the latest RELEASED STABLE NVDA version for the stable store
	# channel. 2026.2 was rejected as "not stable yet"; 2026.1 is the current
	# stable. Do not raise this above the newest stable release.
	"addon_lastTestedNVDAVersion": "2026.1",
	"addon_updateChannel": None,
	"addon_license": "GPL v2",
	"addon_licenseURL": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
}

# Files/directories, relative to the addon/ folder, that make up the package.
addon_package_dirs = ["globalPlugins", "doc", "locale"]

# Python source that should be scanned when generating the translation template.
i18nSources = ["addon/globalPlugins"]
