# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Extract plain, readable text from an uploaded document so it can be handed
to a text-to-speech API.

This runs inside NVDA's bundled Python, which ships a trimmed standard library.
It therefore relies ONLY on ``os``, ``re``, ``zipfile``, ``html`` and ``io`` and
does all XML/HTML handling with regular expressions plus :func:`html.unescape` --
no ``xml.etree``, ``html.parser``, ``docx``, ``ebooklib`` or any third-party
module is imported.
"""

import os
import re
import zipfile
import io

import addonHandler

from . import errors

# The `html` package (for html.unescape) is normally present in NVDA's Python,
# but guard the import and provide a minimal fallback so document upload never
# fails on a trimmed build.
try:
	import html as _html

	def _unescape(text):
		return _html.unescape(text)
except Exception:
	_ENTITIES = {
		"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
		"&apos;": "'", "&#39;": "'", "&nbsp;": " ", "&#160;": " ",
	}

	def _unescape(text):
		for k, v in _ENTITIES.items():
			text = text.replace(k, v)
		# Numeric decimal entities.
		text = re.sub(r"&#(\d+);", lambda m: _safe_chr(int(m.group(1))), text)
		text = re.sub(r"&#[xX]([0-9a-fA-F]+);", lambda m: _safe_chr(int(m.group(1), 16)), text)
		return text

	def _safe_chr(n):
		try:
			return chr(n)
		except (ValueError, OverflowError):
			return ""

try:
	addonHandler.initTranslation()
except Exception:
	# initTranslation raises when not running inside NVDA (e.g. unit tests).
	pass


SUPPORTED_EXTENSIONS = (".txt", ".text", ".md", ".docx", ".epub")


# --- shared regex helpers --------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")
_TRAILING_SPACES_RE = re.compile(r"[ \t]+(?=\n)")
_TRAILING_SPACES_EOL_RE = re.compile(r"[ \t]+$")


def _normalise(text):
	"""Collapse 3+ blank lines to 2 and strip trailing spaces per line."""
	# Normalise line endings first.
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	# Strip trailing spaces before every newline and at the very end.
	text = _TRAILING_SPACES_RE.sub("", text)
	text = _TRAILING_SPACES_EOL_RE.sub("", text)
	# Collapse runs of 3 or more newlines down to exactly two.
	text = _MANY_NEWLINES_RE.sub("\n\n", text)
	return text.strip()


def _strip_tags_to_text(markup):
	"""Remove any remaining tags, unescape entities and return plain text."""
	text = _TAG_RE.sub("", markup)
	return _unescape(text)


# --- plain text ------------------------------------------------------------

def _extract_plain(path):
	try:
		with open(path, "r", encoding="utf-8", errors="replace") as f:
			return _normalise(f.read())
	except OSError as e:
		raise errors.SarvamError(
			# Translators: shown when a text file cannot be read.
			_("Could not read the text file: {error}").format(error=e))


# --- docx ------------------------------------------------------------------

_WT_RE = re.compile(r"<w:t\b[^>]*>(.*?)</w:t>", re.DOTALL)
_WP_END_RE = re.compile(r"</w:p>")
_WBR_RE = re.compile(r"<w:br\b[^>]*/?>")
_WTAB_RE = re.compile(r"<w:tab\b[^>]*/?>")


def _extract_docx(path):
	try:
		with zipfile.ZipFile(path) as zf:
			data = zf.read("word/document.xml")
	except KeyError:
		raise errors.SarvamError(
			# Translators: shown when a .docx is missing its main document part.
			_("This does not look like a valid Word document (word/document.xml is missing)."))
	except (zipfile.BadZipFile, OSError) as e:
		raise errors.SarvamError(
			# Translators: shown when a .docx cannot be opened.
			_("Could not open the Word document: {error}").format(error=e))

	xml = data.decode("utf-8", errors="replace")
	# Mark paragraph and line breaks with newlines BEFORE stripping tags.
	xml = _WP_END_RE.sub("\n", xml)
	xml = _WBR_RE.sub("\n", xml)
	xml = _WTAB_RE.sub("\t", xml)

	# Pull the text out of each run, keeping reading order, and drop everything
	# outside the <w:t> runs (which is markup we do not want to read out).
	parts = []
	pos = 0
	for m in _WT_RE.finditer(xml):
		# Preserve any paragraph breaks that fell between runs.
		between = xml[pos:m.start()]
		if "\n" in between:
			parts.append("\n" * between.count("\n"))
		parts.append(_strip_tags_to_text(m.group(1)))
		pos = m.end()
	# Trailing markup after the last run may still hold paragraph breaks.
	tail = xml[pos:]
	if "\n" in tail:
		parts.append("\n" * tail.count("\n"))

	text = "".join(parts)
	return _normalise(text)


# --- epub ------------------------------------------------------------------

_FULLPATH_RE = re.compile(r'full-path\s*=\s*"([^"]+)"', re.IGNORECASE)
_ITEM_RE = re.compile(r"<item\b([^>]*)/?>", re.IGNORECASE | re.DOTALL)
_ITEMREF_RE = re.compile(r"<itemref\b([^>]*)/?>", re.IGNORECASE | re.DOTALL)
_ID_ATTR_RE = re.compile(r'\bid\s*=\s*"([^"]*)"', re.IGNORECASE)
_HREF_ATTR_RE = re.compile(r'\bhref\s*=\s*"([^"]*)"', re.IGNORECASE)
_IDREF_ATTR_RE = re.compile(r'\bidref\s*=\s*"([^"]*)"', re.IGNORECASE)

_SCRIPT_STYLE_RE = re.compile(
	r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
# Block level tags whose end (or self-close) should become a newline.
_BLOCK_BREAK_RE = re.compile(
	r"</p>|</div>|<br\b[^>]*/?>|</h[1-6]>|</li>|</tr>|</blockquote>",
	re.IGNORECASE)


def _resolve_href(opf_dir, href):
	"""Join an href relative to the OPF directory and normalise slashes."""
	# EPUB hrefs are URL style; drop any fragment and unescape percent-safe text.
	href = href.split("#", 1)[0]
	href = _unescape(href)
	if opf_dir:
		joined = opf_dir + "/" + href
	else:
		joined = href
	# Normalise ../ and ./ segments without touching the filesystem.
	segments = []
	for part in joined.replace("\\", "/").split("/"):
		if part in ("", "."):
			continue
		if part == "..":
			if segments:
				segments.pop()
			continue
		segments.append(part)
	return "/".join(segments)


def _html_to_text(markup):
	"""Turn an (x)html chapter into plain text."""
	markup = _SCRIPT_STYLE_RE.sub(" ", markup)
	markup = _BLOCK_BREAK_RE.sub("\n", markup)
	text = _strip_tags_to_text(markup)
	return text


def _extract_epub(path):
	try:
		zf = zipfile.ZipFile(path)
	except (zipfile.BadZipFile, OSError) as e:
		raise errors.SarvamError(
			# Translators: shown when an .epub cannot be opened.
			_("Could not open the e-book: {error}").format(error=e))

	try:
		# 1. Find the OPF path via META-INF/container.xml.
		try:
			container = zf.read("META-INF/container.xml").decode(
				"utf-8", errors="replace")
		except KeyError:
			raise errors.SarvamError(
				# Translators: shown when an epub has no container manifest.
				_("This does not look like a valid e-book (META-INF/container.xml is missing)."))
		m = _FULLPATH_RE.search(container)
		if not m:
			raise errors.SarvamError(
				# Translators: shown when the epub container has no package path.
				_("The e-book is missing its package file reference."))
		opf_path = _resolve_href("", m.group(1))

		# 2. Read the OPF: build id -> href and the spine reading order.
		try:
			opf = zf.read(opf_path).decode("utf-8", errors="replace")
		except KeyError:
			raise errors.SarvamError(
				# Translators: shown when the epub package file is missing.
				_("The e-book package file could not be found: {path}").format(path=opf_path))

		opf_dir = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""

		id_to_href = {}
		manifest_match = re.search(
			r"<manifest\b[^>]*>(.*?)</manifest>", opf, re.IGNORECASE | re.DOTALL)
		manifest_text = manifest_match.group(1) if manifest_match else opf
		for item in _ITEM_RE.finditer(manifest_text):
			attrs = item.group(1)
			id_m = _ID_ATTR_RE.search(attrs)
			href_m = _HREF_ATTR_RE.search(attrs)
			if id_m and href_m:
				id_to_href[id_m.group(1)] = href_m.group(1)

		spine_match = re.search(
			r"<spine\b[^>]*>(.*?)</spine>", opf, re.IGNORECASE | re.DOTALL)
		spine_text = spine_match.group(1) if spine_match else opf
		spine_ids = []
		for ref in _ITEMREF_RE.finditer(spine_text):
			idref_m = _IDREF_ATTR_RE.search(ref.group(1))
			if idref_m:
				spine_ids.append(idref_m.group(1))

		# 3. Read each spine document in order; be tolerant of failures.
		chunks = []
		for idref in spine_ids:
			href = id_to_href.get(idref)
			if not href:
				continue
			target = _resolve_href(opf_dir, href)
			try:
				raw = zf.read(target)
			except KeyError:
				# Missing spine item: skip rather than fail the whole book.
				continue
			except OSError:
				continue
			try:
				chapter = raw.decode("utf-8", errors="replace")
			except Exception:
				continue
			chunk = _html_to_text(chapter).strip()
			if chunk:
				chunks.append(chunk)

		if not chunks:
			raise errors.SarvamError(
				# Translators: shown when no readable text was found in an epub.
				_("No readable text could be extracted from this e-book."))

		return _normalise("\n\n".join(chunks))
	finally:
		zf.close()


# --- public interface ------------------------------------------------------

def extract_text(path):
	"""Return plain text extracted from a .txt/.md/.docx/.epub file.

	Raises errors.InvalidRequestError for unsupported/missing files and
	errors.SarvamError if parsing fails.
	"""
	if not path or not isinstance(path, str):
		raise errors.InvalidRequestError(
			# Translators: shown when no file path was given.
			_("No document path was provided."))

	if not os.path.isfile(path):
		raise errors.InvalidRequestError(
			# Translators: shown when the document does not exist.
			_("The file could not be found: {path}").format(path=path))

	ext = os.path.splitext(path)[1].lower()

	if ext in (".txt", ".text", ".md"):
		return _extract_plain(path)
	if ext == ".docx":
		return _extract_docx(path)
	if ext == ".epub":
		return _extract_epub(path)

	raise errors.InvalidRequestError(
		# Translators: shown when the file type is not supported. {ext} is the
		# rejected extension and {supported} lists the accepted types.
		_("Unsupported file type '{ext}'. Supported types are: {supported}.").format(
			ext=ext or _("(none)"),
			supported=", ".join(SUPPORTED_EXTENSIONS)))
