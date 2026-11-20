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


PLAIN_EXTENSIONS = (".txt", ".text", ".md", ".markdown", ".log", ".csv", ".tsv",
	".json", ".xml", ".srt", ".vtt", ".py", ".ini")
SUPPORTED_EXTENSIONS = PLAIN_EXTENSIONS + (
	".docx", ".epub", ".html", ".htm", ".xhtml", ".rtf", ".pptx", ".xlsx",
	".odt", ".odp", ".ods")


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


def _extract_subtitles(path):
	"""Subtitles (.srt / .vtt) without cue numbers and timings."""
	text = _extract_plain(path)
	keep = []
	for line in text.split("\n"):
		s = line.strip()
		if not s or s.isdigit() or "-->" in s or s.upper().startswith("WEBVTT"):
			continue
		keep.append(re.sub(r"<[^>]+>", "", s))
	return "\n".join(keep)


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


# --- html ------------------------------------------------------------------

def _extract_html(path):
	try:
		with open(path, "rb") as f:
			raw = f.read()
	except OSError as e:
		raise errors.SarvamError(_("Could not read the file: {error}").format(error=e))
	text = raw.decode("utf-8", errors="replace")
	return _normalise(_html_to_text(text))


# --- rtf -------------------------------------------------------------------

def _extract_rtf(path):
	"""Minimal RTF reader: keeps text, paragraphs and \\uN unicode escapes."""
	try:
		with open(path, "rb") as f:
			rtf = f.read().decode("latin-1")
	except OSError as e:
		raise errors.SarvamError(_("Could not read the file: {error}").format(error=e))
	# Drop font tables, colour tables, pictures and other destinations.
	rtf = re.sub(r"\{\\\*[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", rtf)
	rtf = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info|pict)[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", rtf)

	def uni(m):
		n = int(m.group(1))
		if n < 0:
			n += 65536
		return _safe_chr_any(n)
	rtf = re.sub(r"\\u(-?\d+)\??", uni, rtf)
	rtf = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), rtf)
	rtf = re.sub(r"\\(par|line)\b ?", "\n", rtf)
	rtf = re.sub(r"\\tab\b ?", "\t", rtf)
	rtf = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", rtf)
	rtf = rtf.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
	rtf = rtf.replace("{", "").replace("}", "")
	return _normalise(rtf)


def _safe_chr_any(n):
	try:
		return chr(n)
	except (ValueError, OverflowError):
		return ""


# --- Office Open XML / OpenDocument ----------------------------------------

_AT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.DOTALL)
_AP_END_RE = re.compile(r"</a:p>")


def _extract_pptx(path):
	try:
		zf = zipfile.ZipFile(path)
	except (zipfile.BadZipFile, OSError) as e:
		raise errors.SarvamError(_("Could not open the presentation: {error}").format(error=e))
	with zf:
		slides = [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
		slides.sort(key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
		out = []
		for i, name in enumerate(slides, 1):
			xml = zf.read(name).decode("utf-8", errors="replace")
			xml = _AP_END_RE.sub("\n", xml)
			lines = []
			for chunk in xml.split("\n"):
				text = "".join(_unescape(t) for t in _AT_RE.findall(chunk)).strip()
				if text:
					lines.append(text)
			out.append("## " + (_("Slide {n}").format(n=i)) + "\n\n" + "\n".join(lines))
		if not out:
			raise errors.SarvamError(_("No slides were found in this presentation."))
		return _normalise("\n\n".join(out))


def _col_index(ref):
	letters = re.match(r"([A-Z]+)", ref or "A")
	n = 0
	for ch in (letters.group(1) if letters else "A"):
		n = n * 26 + (ord(ch) - 64)
	return n - 1


def _extract_xlsx(path):
	"""Every sheet as a Markdown table (so structure survives TTS/AI/export)."""
	try:
		zf = zipfile.ZipFile(path)
	except (zipfile.BadZipFile, OSError) as e:
		raise errors.SarvamError(_("Could not open the spreadsheet: {error}").format(error=e))
	with zf:
		shared = []
		if "xl/sharedStrings.xml" in zf.namelist():
			sx = zf.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
			for si in re.findall(r"<si>(.*?)</si>", sx, re.DOTALL):
				shared.append(_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.DOTALL))))
		names = {}
		if "xl/workbook.xml" in zf.namelist():
			wb = zf.read("xl/workbook.xml").decode("utf-8", errors="replace")
			for i, m in enumerate(re.finditer(r'<sheet\b[^>]*name="([^"]*)"', wb), 1):
				names[i] = _unescape(m.group(1))
		sheets = [n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
		sheets.sort(key=lambda n: int(re.search(r"sheet(\d+)", n).group(1)))
		out = []
		for name in sheets:
			idx = int(re.search(r"sheet(\d+)", name).group(1))
			xml = zf.read(name).decode("utf-8", errors="replace")
			rows = []
			for row in re.findall(r"<row\b[^>]*>(.*?)</row>", xml, re.DOTALL):
				cells = {}
				for m in re.finditer(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", row, re.DOTALL):
					attrs, inner = m.group(1), m.group(2) or ""
					ref = re.search(r'\br="([A-Z]+)\d+"', attrs)
					typ = re.search(r'\bt="(\w+)"', attrs)
					val = re.search(r"<v>(.*?)</v>", inner, re.DOTALL)
					if typ and typ.group(1) == "inlineStr":
						text = "".join(re.findall(r"<t[^>]*>(.*?)</t>", inner, re.DOTALL))
					elif typ and typ.group(1) == "s" and val:
						try:
							text = shared[int(val.group(1))]
						except (ValueError, IndexError):
							text = ""
					else:
						text = val.group(1) if val else ""
					cells[_col_index(ref.group(1) if ref else "A")] = _unescape(text).replace("|", "/").strip()
				if cells:
					width = max(cells) + 1
					rows.append([cells.get(i, "") for i in range(width)])
			if not rows:
				continue
			width = max(len(r) for r in rows)
			rows = [r + [""] * (width - len(r)) for r in rows]
			lines = ["## " + names.get(idx, _("Sheet {n}").format(n=idx)), ""]
			lines.append("| " + " | ".join(rows[0]) + " |")
			lines.append("|" + "---|" * width)
			for r in rows[1:]:
				lines.append("| " + " | ".join(r) + " |")
			out.append("\n".join(lines))
		if not out:
			raise errors.SarvamError(_("No data was found in this spreadsheet."))
		return "\n\n".join(out)


def _extract_odf(path):
	"""OpenDocument text, presentation or spreadsheet (content.xml)."""
	try:
		with zipfile.ZipFile(path) as zf:
			xml = zf.read("content.xml").decode("utf-8", errors="replace")
	except (KeyError, zipfile.BadZipFile, OSError) as e:
		raise errors.SarvamError(_("Could not open the document: {error}").format(error=e))
	xml = re.sub(r"</text:(p|h)>|<text:line-break/>|</table:table-row>", "\n", xml)
	xml = re.sub(r"</table:table-cell>", "\t", xml)
	xml = re.sub(r"<text:tab/>", "\t", xml)
	xml = re.sub(r'<text:s(?: text:c="(\d+)")?/>', lambda m: " " * int(m.group(1) or 1), xml)
	return _normalise(_strip_tags_to_text(xml))


# --- public interface ------------------------------------------------------

def extract_text(path):
	"""Return plain text extracted from any supported document.

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

	if ext in (".srt", ".vtt"):
		return _extract_subtitles(path)
	if ext in PLAIN_EXTENSIONS:
		return _extract_plain(path)
	if ext == ".docx":
		return _extract_docx(path)
	if ext == ".epub":
		return _extract_epub(path)
	if ext in (".html", ".htm", ".xhtml"):
		return _extract_html(path)
	if ext == ".rtf":
		return _extract_rtf(path)
	if ext == ".pptx":
		return _extract_pptx(path)
	if ext == ".xlsx":
		return _extract_xlsx(path)
	if ext in (".odt", ".odp", ".ods"):
		return _extract_odf(path)

	raise errors.InvalidRequestError(
		# Translators: shown when the file type is not supported. {ext} is the
		# rejected extension and {supported} lists the accepted types.
		_("Unsupported file type '{ext}'. Supported types are: {supported}.").format(
			ext=ext or _("(none)"),
			supported=", ".join(SUPPORTED_EXTENSIONS)))
