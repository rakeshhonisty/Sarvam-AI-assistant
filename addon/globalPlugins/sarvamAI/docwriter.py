# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Export recognised / generated text to files.

Supports plain text (.txt) and Microsoft Word (.docx). A .docx is an Open XML
package (a ZIP of XML parts), so it is produced with the standard library only
- no python-docx or other third-party dependency."""

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


_CONTENT_TYPES = (
	'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
	'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
	'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
	'<Default Extension="xml" ContentType="application/xml"/>'
	'<Override PartName="/word/document.xml" '
	'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
	'</Types>')

_RELS = (
	'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
	'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
	'<Relationship Id="rId1" '
	'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
	'Target="word/document.xml"/></Relationships>')


def _paragraph(line):
	if line == "":
		return '<w:p/>'
	return (
		'<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
		% _xml_escape(line))


def _document_xml(text):
	paragraphs = "".join(_paragraph(line) for line in (text or "").split("\n"))
	return (
		'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
		'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
		'<w:body>%s<w:sectPr/></w:body></w:document>' % paragraphs)


def write_docx(text, path):
	"""Write ``text`` to ``path`` as a minimal, valid Microsoft Word document."""
	try:
		with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
			z.writestr("[Content_Types].xml", _CONTENT_TYPES)
			z.writestr("_rels/.rels", _RELS)
			z.writestr("word/document.xml", _document_xml(text))
		return path
	except OSError as e:
		raise errors.SarvamError(_("Could not save the Word document: {err}").format(err=e))
