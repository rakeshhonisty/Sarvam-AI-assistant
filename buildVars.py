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
		"visually-impaired users. Version 2.0: Bulbul v4 Flash persona voices "
		"chosen by gender, purpose and language; Saaras v4 speech to text with "
		"key terms, speaker separation and subtitles; translation of text and of "
		"whole PDF, Word, Excel and PowerPoint files in their own format; Sarvam "
		"Document AI OCR and data extraction to Excel or CSV in 23 languages; "
		"the AI Workforce and a tool-using Sarvam Agent; AI vision to describe "
		"images and the screen; and model switching between Sarvam 105B and "
		"Sarvam's open models (GLM 5.3, Gemma 4, DeepSeek V4.1 Flash and more). "
		"Upload almost any file and download results as Word, Markdown, HTML, "
		"RTF, Excel, CSV, JSON, text or audio. Fully keyboard accessible."
	),
	"addon_version": "2.0",
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
