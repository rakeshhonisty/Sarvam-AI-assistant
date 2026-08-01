# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Export recognised / generated text to files.

Supports plain text (.txt) and Microsoft Word (.docx). A .docx is an Open XML
package (a ZIP of XML parts), produced with the standard library only - no
python-docx dependency.

Two DOCX writers are provided:

* :func:`write_docx` - each line becomes a paragraph (plain text).
* :func:`write_docx_from_markdown` - understands the Markdown that Sarvam's
  Document Intelligence (OCR) and the AI features return, and preserves
  structure: headings, bullet / numbered lists, and **real Word tables**
  (pipe tables). This keeps document layout (tables, columns, reading order)
  intact when saving OCR or translation output to Word.
"""

import re
import zipfile

from . import errors

try:
	import addonHandler
	addonHandler.initTranslation()
except Exception:
	pass


def write_txt(text, path):
	"""Write ``text`` to ``path`` as UTF-8 plain text."""
	try:
		with open(path, "w", encoding="utf-8") as f:
			f.write(text or "")
		return path
	except OSError as e:
		raise errors.SarvamError(_("Could not save the text file: {err}").format(err=e))


def _xml_escape(s):
	return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
		.replace('"', "&quot;").replace("'", "&apos;"))


# --- Open XML package parts -------------------------------------------------
_CONTENT_TYPES = (
	'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
	'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
	'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
	'<Default Extension="xml" ContentType="application/xml"/>'
	'<Override PartName="/word/document.xml" '
	'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
	'<Override PartName="/word/styles.xml" '
	'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
	'</Types>')

_RELS = (
	'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
	'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
	'<Relationship Id="rId1" '
	'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
	'Target="word/document.xml"/></Relationships>')

_DOC_RELS = (
	'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
	'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
	'<Relationship Id="rId1" '
	'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
	'Target="styles.xml"/></Relationships>')


def _styles_xml():
	# Define Normal plus Heading1..Heading6 with outline levels, so headings
	# are real Word headings (navigable by screen readers and Word's outline).
	parts = [
		'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
		'<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
		'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>',
	]
	sizes = {1: 32, 2: 28, 3: 26, 4: 24, 5: 22, 6: 20}
	for lvl in range(1, 7):
		half = sizes[lvl]
		parts.append(
			'<w:style w:type="paragraph" w:styleId="Heading%d">'
			'<w:name w:val="heading %d"/><w:basedOn w:val="Normal"/>'
			'<w:pPr><w:outlineLvl w:val="%d"/></w:pPr>'
			'<w:rPr><w:b/><w:sz w:val="%d"/></w:rPr></w:style>'
			% (lvl, lvl, lvl - 1, half))
	parts.append('</w:styles>')
	return "".join(parts)


def _run(text):
	return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % _xml_escape(text)


def _para(text, style=None):
	ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else ''
	if text == "":
		return '<w:p>%s</w:p>' % ppr
	return '<w:p>%s%s</w:p>' % (ppr, _run(text))


def _table(rows):
	"""``rows`` is a list of lists of cell strings."""
	if not rows:
		return ""
	out = [
		'<w:tbl><w:tblPr><w:tblBorders>'
		'<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
		'</w:tblBorders></w:tblPr>']
	for r in rows:
		out.append('<w:tr>')
		for cell in r:
			out.append('<w:tc><w:tcPr/>%s</w:tc>' % _para(cell))
		out.append('</w:tr>')
	out.append('</w:tbl>')
	# Word needs an empty paragraph after a table.
	out.append(_para(""))
	return "".join(out)


# --- Markdown parsing (headings / lists / tables) ---------------------------
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBER_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _split_table_row(line):
	line = line.strip()
	if line.startswith("|"):
		line = line[1:]
	if line.endswith("|"):
		line = line[:-1]
	return [c.strip() for c in line.split("|")]


def _markdown_body(md):
	"""Turn Markdown into a document.xml body preserving structure."""
	lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
	body = []
	i = 0
	n = len(lines)
	while i < n:
		line = lines[i]
		# Table: a row of pipes followed by a separator row.
		if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
			header = _split_table_row(line)
			rows = [header]
			i += 2
			while i < n and "|" in lines[i] and lines[i].strip():
				rows.append(_split_table_row(lines[i]))
				i += 1
			body.append(_table(rows))
			continue
		m = _HEADING_RE.match(line)
		if m:
			level = len(m.group(1))
			body.append(_para(_strip_inline(m.group(2)), style="Heading%d" % level))
			i += 1
			continue
		m = _BULLET_RE.match(line)
		if m:
			body.append(_para("• " + _strip_inline(m.group(1))))
			i += 1
			continue
		m = _NUMBER_RE.match(line)
		if m:
			body.append(_para(_strip_inline(line.strip())))
			i += 1
			continue
		body.append(_para(_strip_inline(line)))
		i += 1
	return "".join(body)


def _strip_inline(text):
	# Remove common inline Markdown emphasis markers for clean Word text.
	text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
	text = re.sub(r"__(.+?)__", r"\1", text)
	text = re.sub(r"(?<!\*)\*(?!\s)(.+?)\*", r"\1", text)
	text = re.sub(r"`(.+?)`", r"\1", text)
	return text


def _document_xml(body):
	return (
		'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
		'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
		'<w:body>%s<w:sectPr/></w:body></w:document>' % body)


def _write_package(path, body):
	try:
		with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
			z.writestr("[Content_Types].xml", _CONTENT_TYPES)
			z.writestr("_rels/.rels", _RELS)
			z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
			z.writestr("word/styles.xml", _styles_xml())
			z.writestr("word/document.xml", _document_xml(body))
		return path
	except OSError as e:
		raise errors.SarvamError(_("Could not save the Word document: {err}").format(err=e))


def write_docx(text, path):
	"""Write ``text`` to ``path`` as a Word document (one paragraph per line)."""
	body = "".join(_para(line) for line in (text or "").split("\n"))
	return _write_package(path, body)


def write_docx_from_markdown(md_text, path):
	"""Write Markdown to a Word document, preserving headings, lists and tables."""
	return _write_package(path, _markdown_body(md_text))
