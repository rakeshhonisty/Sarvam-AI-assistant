# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""One place that knows how to read every file type the add-on accepts.

Every dialog with an Upload button uses :func:`read_any`, so a user can give
any feature any file:

* documents (TXT, Markdown, Word, EPUB, HTML, RTF, PowerPoint, Excel,
  OpenDocument, CSV, JSON, subtitles) are read directly on this computer;
* PDFs, scans, photos and ZIPs of page images go through Sarvam Document AI;
* audio and video sound tracks are transcribed with Sarvam speech to text.
"""

import os

from . import constants
from . import textextract

try:
	import addonHandler
	addonHandler.initTranslation()
except Exception:
	pass

KIND_TEXT = "text"
KIND_DOCUMENT = "document"
KIND_AUDIO = "audio"
KIND_IMAGE = "image"


def kind_of(path):
	ext = os.path.splitext(path)[1].lower()
	if ext in constants.AUDIO_EXTENSIONS:
		return KIND_AUDIO
	if ext in constants.IMAGE_EXTENSIONS:
		return KIND_IMAGE
	if ext in (".pdf", ".zip"):
		return KIND_DOCUMENT
	if ext in textextract.SUPPORTED_EXTENSIONS:
		return KIND_TEXT
	return None


def all_extensions(text=True, documents=True, audio=True, images=True):
	exts = []
	if text:
		exts += list(textextract.SUPPORTED_EXTENSIONS)
	if documents:
		exts += [".pdf", ".zip"]
	if images:
		exts += list(constants.IMAGE_EXTENSIONS)
	if audio:
		exts += list(constants.AUDIO_EXTENSIONS)
	seen = []
	for e in exts:
		if e not in seen:
			seen.append(e)
	return seen


def wildcard(label, exts):
	"""A wx file-dialog wildcard: the given types first, then All files."""
	pattern = ";".join("*" + e for e in exts)
	return "%s|%s|%s|*.*" % (label, pattern, _("All files (*.*)"))


def read_any(path, client, conf, cancel=None, progress=None):
	"""Return the text content of ``path`` whatever its type."""
	kind = kind_of(path)
	if kind == KIND_AUDIO:
		res = client.transcribe(
			path, model=conf.get("sttModel"), language_code=conf.get("sttLanguage"),
			cancel=cancel, progress=progress)
		return res.get("transcript", "")
	if kind in (KIND_DOCUMENT, KIND_IMAGE):
		res = client.document_ocr(
			path, language=conf.get("ocrLanguage"),
			output_format=conf.get("ocrOutputFormat") or constants.DEFAULT_OCR_OUTPUT_FORMAT,
			cancel=cancel, progress=progress)
		return res.get("text", "")
	return textextract.extract_text(path)


def read_image_bytes(path, max_bytes=6 * 1024 * 1024):
	"""Load an image for a vision model as ``(bytes, mime)``.

	PNG/JPEG/WebP/GIF go through unchanged when small enough; anything else
	(or anything too large for the 10 MB request limit) is re-encoded to JPEG.
	"""
	from . import imaging
	ext = os.path.splitext(path)[1].lower()
	mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
		".webp": "image/webp", ".gif": "image/gif"}.get(ext)
	if mime and os.path.getsize(path) <= max_bytes:
		with open(path, "rb") as f:
			return f.read(), mime
	jpeg_path, _w, _h = imaging.image_to_jpeg(path)
	try:
		with open(jpeg_path, "rb") as f:
			return f.read(), "image/jpeg"
	finally:
		try:
			os.remove(jpeg_path)
		except OSError:
			pass
