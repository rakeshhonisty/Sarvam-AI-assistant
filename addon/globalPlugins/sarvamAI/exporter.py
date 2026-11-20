# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Save results in whatever format the user wants ("Download as ...").

All writers are dependency-free (standard library only, as NVDA ships a
trimmed Python). Markdown structure produced by Sarvam - headings, lists and
pipe tables - is turned into real structure in every rich format: Word
headings and tables, HTML headings and tables, Excel sheets and CSV rows.

Formats:

=========  ===============================================================
txt        Plain text (UTF-8)
docx       Microsoft Word, with real headings and tables
md         Markdown, exactly as Sarvam produced it
html       Web page, accessible headings and tables, opens in any browser
rtf        Rich Text, opens in WordPad / Word
xlsx       Microsoft Excel - every table becomes a sheet
csv        Comma separated values (UTF-8 with BOM, opens in Excel)
json       Structured data: the text plus its tables (and timings)
srt        Subtitles, from a timestamped transcript
=========  ===============================================================
"""

import json
import re
import zipfile

from . import errors
from . import docwriter

try:
	import addonHandler
	addonHandler.initTranslation()
except Exception:
	pass

# (key, extension, label). Labels are wrapped in _() at display time.
FORMATS = (
	("txt", ".txt", "Plain text (.txt)"),
	("docx", ".docx", "Word document (.docx)"),
	("md", ".md", "Markdown (.md)"),
	("html", ".html", "Web page (.html)"),
	("rtf", ".rtf", "Rich text (.rtf)"),
	("xlsx", ".xlsx", "Excel workbook, tables only (.xlsx)"),
	("csv", ".csv", "CSV spreadsheet, tables only (.csv)"),
	("json", ".json", "JSON data (.json)"),
	("srt", ".srt", "Subtitles (.srt)"),
)
TEXT_FORMATS = ("txt", "docx", "md", "html", "rtf", "json")
TABLE_FORMATS = ("xlsx", "csv")


def format_keys(include_tables=True, include_srt=False):
	keys = [k for k, _e, _l in FORMATS if k in TEXT_FORMATS]
	if include_tables:
		keys += list(TABLE_FORMATS)
	if include_srt:
		keys.append("srt")
	return keys


def extension(fmt):
	for k, e, _l in FORMATS:
		if k == fmt:
			return e
	return ".txt"


def label(fmt):
	for k, _e, lab in FORMATS:
		if k == fmt:
			return lab
	return fmt


# --- markdown helpers ----------------------------------------------------------
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBER_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")


def _row(line):
	line = line.strip()
	if line.startswith("|"):
		line = line[1:]
	if line.endswith("|"):
		line = line[:-1]
	return [c.strip() for c in line.split("|")]


def tables_from_markdown(md):
	"""Every pipe table in ``md`` as ``[(title, rows)]``; the title is the
	nearest heading above the table."""
	lines = (md or "").replace("\r\n", "\n").split("\n")
	out = []
	title = None
	i = 0
	while i < len(lines):
		h = _HEADING_RE.match(lines[i])
		if h:
			title = h.group(2).strip()
		if "|" in lines[i] and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
			rows = [_row(lines[i])]
			i += 2
			while i < len(lines) and "|" in lines[i] and lines[i].strip():
				rows.append(_row(lines[i]))
				i += 1
			out.append((title or "Table %d" % (len(out) + 1), rows))
			continue
		i += 1
	return out


def _inline(text):
	text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
	text = re.sub(r"__(.+?)__", r"\1", text)
	text = re.sub(r"`(.+?)`", r"\1", text)
	return text


def _esc(s):
	return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
		.replace('"', "&quot;"))


def markdown_to_html(md, title="Sarvam AI"):
	lines = (md or "").replace("\r\n", "\n").split("\n")
	body = []
	in_ul = in_ol = False

	def close_lists():
		nonlocal in_ul, in_ol
		if in_ul:
			body.append("</ul>")
			in_ul = False
		if in_ol:
			body.append("</ol>")
			in_ol = False

	i = 0
	while i < len(lines):
		line = lines[i]
		if "|" in line and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
			close_lists()
			rows = [_row(line)]
			i += 2
			while i < len(lines) and "|" in lines[i] and lines[i].strip():
				rows.append(_row(lines[i]))
				i += 1
			body.append("<table>")
			body.append("<thead><tr>%s</tr></thead>" % "".join(
				'<th scope="col">%s</th>' % _esc(_inline(c)) for c in rows[0]))
			body.append("<tbody>")
			for r in rows[1:]:
				body.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _esc(_inline(c)) for c in r))
			body.append("</tbody></table>")
			continue
		h = _HEADING_RE.match(line)
		b = _BULLET_RE.match(line)
		n = _NUMBER_RE.match(line)
		if h:
			close_lists()
			lvl = len(h.group(1))
			body.append("<h%d>%s</h%d>" % (lvl, _esc(_inline(h.group(2))), lvl))
		elif b:
			if in_ol:
				close_lists()
			if not in_ul:
				body.append("<ul>")
				in_ul = True
			body.append("<li>%s</li>" % _esc(_inline(b.group(1))))
		elif n:
			if in_ul:
				close_lists()
			if not in_ol:
				body.append("<ol>")
				in_ol = True
			body.append("<li>%s</li>" % _esc(_inline(n.group(2))))
		elif line.strip():
			close_lists()
			body.append("<p>%s</p>" % _esc(_inline(line)))
		else:
			close_lists()
		i += 1
	close_lists()
	return (
		'<!DOCTYPE html>\n<html lang="und">\n<head>\n<meta charset="utf-8">\n'
		'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
		"<title>%s</title>\n<style>body{font-family:sans-serif;max-width:50em;margin:1em auto;"
		"padding:0 1em;line-height:1.5}table{border-collapse:collapse}"
		"th,td{border:1px solid #888;padding:.3em .6em;text-align:left}</style>\n"
		"</head>\n<body>\n%s\n</body>\n</html>\n" % (_esc(title), "\n".join(body)))


def _rtf(text):
	out = ["{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0 Nirmala UI;}}\\f0\\fs24 "]
	for ch in text.replace("\r\n", "\n"):
		o = ord(ch)
		if ch == "\n":
			out.append("\\par\n")
		elif ch in "\\{}":
			out.append("\\" + ch)
		elif o < 128:
			out.append(ch)
		else:
			# RTF \uN takes a signed 16-bit value; astral characters are
			# written as their UTF-16 surrogate pair.
			for unit in _utf16_units(o):
				out.append("\\u%d?" % (unit - 65536 if unit > 32767 else unit))
	out.append("}")
	return "".join(out)


def _utf16_units(o):
	if o < 0x10000:
		return [o]
	o -= 0x10000
	return [0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)]


def _csv_cell(value):
	v = str(value)
	if any(c in v for c in ',"\r\n'):
		v = '"' + v.replace('"', '""') + '"'
	return v


def _csv(tables, text):
	"""RFC 4180 CSV (no csv module: NVDA's trimmed stdlib may lack it)."""
	out = []

	def row(cells):
		out.append(",".join(_csv_cell(c) for c in cells))

	if tables:
		for k, (title, rows) in enumerate(tables):
			if len(tables) > 1:
				if k:
					out.append("")
				row([title])
			for r in rows:
				row(r)
	else:
		for line in (text or "").split("\n"):
			if line.strip():
				row([line])
	return "\ufeff" + "\r\n".join(out) + "\r\n"


def _xlsx(tables, text):
	"""A minimal, valid .xlsx: one sheet per table (inline strings)."""
	if not tables:
		tables = [("Text", [[line] for line in (text or "").split("\n") if line.strip()] or [[""]])]
	sheets = []
	used = set()
	for idx, (title, rows) in enumerate(tables, 1):
		name = re.sub(r"[\[\]\*\?/\\:]", " ", title or ("Sheet%d" % idx)).strip()[:31] or "Sheet%d" % idx
		base = name
		k = 2
		while name.lower() in used:
			name = (base[:28] + " %d" % k)
			k += 1
		used.add(name.lower())
		sheets.append((name, rows))

	def col(n):
		s = ""
		n += 1
		while n:
			n, r = divmod(n - 1, 26)
			s = chr(65 + r) + s
		return s

	def sheet_xml(rows):
		out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
			'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
		for r_i, row in enumerate(rows, 1):
			out.append('<row r="%d">' % r_i)
			for c_i, val in enumerate(row):
				ref = "%s%d" % (col(c_i), r_i)
				v = str(val)
				num = re.match(r"^-?\d+(\.\d+)?$", v.replace(",", "")) and len(v) < 16 and not v.startswith("0")
				if num and r_i > 1:
					out.append('<c r="%s"><v>%s</v></c>' % (ref, v.replace(",", "")))
				else:
					out.append('<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
						% (ref, _esc(v)))
			out.append("</row>")
		out.append("</sheetData></worksheet>")
		return "".join(out)

	ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
		'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
		'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
		'<Default Extension="xml" ContentType="application/xml"/>'
		'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
	wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
		'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
		'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
	rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
		'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
	for i, (name, _rows) in enumerate(sheets, 1):
		ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" '
			'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
		wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_esc(name), i, i))
		rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
			'Target="worksheets/sheet%d.xml"/>' % (i, i))
	ct.append("</Types>")
	wb.append("</sheets></workbook>")
	rels.append("</Relationships>")
	root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
		'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
		'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
		'Target="xl/workbook.xml"/></Relationships>')
	return ct, wb, rels, root_rels, [(i, sheet_xml(rows)) for i, (_n, rows) in enumerate(sheets, 1)]


def _srt_time(t):
	t = max(0.0, float(t or 0))
	h = int(t // 3600)
	m = int((t % 3600) // 60)
	s = int(t % 60)
	ms = int(round((t - int(t)) * 1000))
	if ms == 1000:
		s, ms = s + 1, 0
	return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _srt(segments):
	timed = [s for s in (segments or []) if s.get("start") is not None]
	if not timed:
		raise errors.InvalidRequestError(_(
			"Subtitles need timings. Tick 'Include timings' (or 'Separate speakers') "
			"and transcribe again."))
	out = []
	for i, s in enumerate(timed, 1):
		end = s.get("end") if s.get("end") is not None else (s["start"] + 3)
		text = s.get("text", "")
		if s.get("speaker"):
			text = "%s: %s" % (s["speaker"], text)
		out.append("%d\n%s --> %s\n%s\n" % (i, _srt_time(s["start"]), _srt_time(end), text))
	return "\n".join(out)


def export(text, path, fmt, title="Sarvam AI", segments=None, markdown=True):
	"""Write ``text`` to ``path`` in format ``fmt``. Returns ``path``."""
	text = text or ""
	try:
		if fmt == "docx":
			if markdown:
				return docwriter.write_docx_from_markdown(text, path)
			return docwriter.write_docx(text, path)
		if fmt in ("txt", "md"):
			return docwriter.write_txt(text, path)
		if fmt == "html":
			with open(path, "w", encoding="utf-8") as f:
				f.write(markdown_to_html(text, title=title))
			return path
		if fmt == "rtf":
			with open(path, "w", encoding="ascii") as f:
				f.write(_rtf(text))
			return path
		if fmt == "csv":
			with open(path, "w", encoding="utf-8", newline="") as f:
				f.write(_csv(tables_from_markdown(text), text))
			return path
		if fmt == "xlsx":
			ct, wb, rels, root_rels, sheets = _xlsx(tables_from_markdown(text), text)
			with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
				z.writestr("[Content_Types].xml", "".join(ct))
				z.writestr("_rels/.rels", root_rels)
				z.writestr("xl/workbook.xml", "".join(wb))
				z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
				for i, xml in sheets:
					z.writestr("xl/worksheets/sheet%d.xml" % i, xml)
			return path
		if fmt == "json":
			data = {"title": title, "text": text}
			tables = tables_from_markdown(text)
			if tables:
				data["tables"] = [{"title": t, "rows": r} for t, r in tables]
			if segments:
				data["segments"] = segments
			with open(path, "w", encoding="utf-8") as f:
				json.dump(data, f, ensure_ascii=False, indent=2)
			return path
		if fmt == "srt":
			with open(path, "w", encoding="utf-8") as f:
				f.write(_srt(segments))
			return path
	except errors.SarvamError:
		raise
	except OSError as e:
		raise errors.SarvamError(_("Could not save the file: {err}").format(err=e))
	raise errors.InvalidRequestError(_("Unknown file format: {fmt}").format(fmt=fmt))
