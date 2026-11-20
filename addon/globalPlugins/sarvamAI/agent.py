# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""The Sarvam Agent: a tool-using assistant that does multi-step work.

Sarvam's Chat Completions V2 API supports OpenAI-style function calling on
Sarvam 105B and the open models (GLM, Gemma, DeepSeek, Kimi, Qwen). The agent
gives the model a small set of tools that run *inside the add-on*:

* read the files the user attached,
* translate / transliterate / detect language (Sarvam text APIs),
* create a speech audio file with the right Bulbul voice for a gender and
  purpose (Sarvam text to speech),
* save a document in any format (TXT, Word, Markdown, HTML, RTF, Excel,
  CSV, JSON).

So one request such as "Translate the attached letter to Kannada, save it as a
Word file and make an MP3 of it read by a female narration voice" is carried
out end to end. Every step is reported to the user as it happens.

Safety: the agent can only *write* inside the add-on's output folder (file
names are sanitised and never overwrite an existing file) and can only *read*
the files the user attached. It cannot run programs, browse, or delete
anything. The number of steps per request is capped.
"""

import json
import os
import re
import time

from . import constants
from . import errors
from . import exporter
from . import logger
from . import models
from . import ttsstyles

try:
	import addonHandler
	addonHandler.initTranslation()
except Exception:
	pass

_READ_LIMIT = 60000
_KNOWN_EXTS = (".txt", ".md", ".docx", ".html", ".htm", ".rtf", ".xlsx", ".csv",
	".json", ".srt", ".mp3", ".wav", ".flac", ".aac", ".pdf")


def _fn(name, description, properties, required=()):
	return {"type": "function", "function": {
		"name": name, "description": description,
		"parameters": {"type": "object", "properties": properties,
			"required": list(required), "additionalProperties": False}}}


_LANG_DESC = ("Sarvam language code such as hi-IN, kn-IN, ta-IN, te-IN, ml-IN, mr-IN, "
	"bn-IN, gu-IN, pa-IN, od-IN or en-IN.")

TOOLS = (
	_fn("list_attached_files",
		"List the files the user attached, with their index, name and length.", {}),
	_fn("read_attached_file",
		"Read the text of an attached file (already converted from PDF, image, "
		"Word, audio etc.).",
		{"index": {"type": "integer", "description": "File index from list_attached_files, starting at 1."},
			"start": {"type": "integer", "description": "Character offset to start from (default 0)."}},
		("index",)),
	_fn("translate_text", "Translate text between Indian languages and English.",
		{"text": {"type": "string"},
			"target_language": {"type": "string", "description": _LANG_DESC},
			"source_language": {"type": "string", "description": "Source code, or 'auto'."}},
		("text", "target_language")),
	_fn("transliterate_text",
		"Convert text to another script without translating (for example Hindi in Latin letters).",
		{"text": {"type": "string"},
			"target_language": {"type": "string", "description": _LANG_DESC}},
		("text", "target_language")),
	_fn("detect_language", "Identify the language and script of some text.",
		{"text": {"type": "string"}}, ("text",)),
	_fn("create_speech_file",
		"Turn text into a speech audio file with a Sarvam Bulbul voice and save it.",
		{"text": {"type": "string"},
			"language": {"type": "string", "description": _LANG_DESC + " Use 'auto' to detect."},
			"gender": {"type": "string", "enum": ["Female", "Male"]},
			"purpose": {"type": "string", "enum": list(ttsstyles.PURPOSE_KEYS),
				"description": "Nature of the work the voice is for."},
			"file_name": {"type": "string", "description": "File name without folder."},
			"audio_format": {"type": "string", "enum": ["mp3", "wav", "flac", "aac"]}},
		("text", "file_name")),
	_fn("save_document",
		"Save text as a file. Markdown headings, lists and pipe tables become real "
		"structure in docx/html/xlsx/csv.",
		{"content": {"type": "string"},
			"file_name": {"type": "string", "description": "File name without folder."},
			"format": {"type": "string", "enum": list(exporter.format_keys(include_tables=True))}},
		("content", "file_name", "format")),
	_fn("get_current_date_time", "Get the current local date and time.", {}),
)


def safe_file_name(name, ext):
	"""A plain file name (no folders, no reserved characters) ending in ``ext``."""
	name = os.path.basename((name or "").replace("\\", "/"))
	name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
	if not name:
		name = "sarvam-agent"
	root, cur = os.path.splitext(name)
	if cur.lower() not in _KNOWN_EXTS:
		root = name
	name = (root or "sarvam-agent") + ext
	reserved = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}
	if os.path.splitext(name)[0].lower() in reserved:
		name = "_" + name
	return name[:150]


class AgentTools:
	"""Executes tool calls for one agent run."""

	def __init__(self, client, conf, attachments, out_dir, cancel=None):
		self._cli = client
		self._conf = conf
		self._attachments = attachments  # list of (name, text)
		self._out_dir = out_dir
		self._cancel = cancel
		self.saved_files = []

	def _unique(self, name):
		from .client import unique_path
		os.makedirs(self._out_dir, exist_ok=True)
		return unique_path(os.path.join(self._out_dir, name))

	def run(self, name, args):
		fn = getattr(self, "tool_" + name, None)
		if fn is None:
			return {"error": "Unknown tool %s" % name}
		try:
			return fn(**(args or {}))
		except errors.CancelledError:
			raise
		except TypeError as e:
			return {"error": "Bad arguments: %s" % e}
		except errors.SarvamError as e:
			return {"error": e.message}
		except Exception as e:  # noqa: BLE001
			logger.exception("Agent tool %s failed" % name)
			return {"error": str(e)}

	# -- tools ---------------------------------------------------------------
	def tool_list_attached_files(self):
		return {"files": [{"index": i, "name": n, "characters": len(t)}
			for i, (n, t) in enumerate(self._attachments, 1)]}

	def tool_read_attached_file(self, index, start=0):
		try:
			name, text = self._attachments[int(index) - 1]
		except (IndexError, ValueError, TypeError):
			return {"error": "No attached file with index %s." % index}
		start = max(0, int(start or 0))
		chunk = text[start:start + _READ_LIMIT]
		res = {"name": name, "start": start, "text": chunk, "total_characters": len(text)}
		if start + _READ_LIMIT < len(text):
			res["note"] = "Truncated; call again with start=%d for more." % (start + _READ_LIMIT)
		return res

	def tool_translate_text(self, text, target_language, source_language="auto"):
		out = self._cli.translate_long(
			text, source_language_code=source_language or "auto",
			target_language_code=target_language,
			model=self._conf.get("translateModel"), cancel=self._cancel)
		return {"translated_text": out, "target_language": target_language}

	def tool_transliterate_text(self, text, target_language):
		r = self._cli.transliterate(text, "auto", target_language, cancel=self._cancel)
		return {"transliterated_text": r.get("transliterated_text", "")}

	def tool_detect_language(self, text):
		r = self._cli.detect_language(text, cancel=self._cancel)
		code = r.get("language_code")
		return {"language_code": code, "language": constants.language_name(code or ""),
			"script_code": r.get("script_code")}

	def tool_create_speech_file(self, text, file_name, language="auto", gender=None,
			purpose=None, audio_format="mp3"):
		fmt = audio_format if audio_format in constants.TTS_OUTPUT_CODECS else "mp3"
		lang = language
		if not lang or lang in ("auto", "unknown"):
			lang = constants.to_tts_language(
				self._cli.detect_language(text, cancel=self._cancel).get("language_code"))
		gender = gender if gender in ttsstyles.GENDERS else (self._conf.get("ttsGender") or "Female")
		purpose = purpose if purpose in ttsstyles.PURPOSE_KEYS else (self._conf.get("ttsStyle") or "conversational")
		model = self._conf.get("ttsModel") or models.DEFAULT_TTS_MODEL
		if not models.tts_supports_language(model, lang):
			model = models.FALLBACK_TTS_MODEL
		voice = ttsstyles.default_voice(gender, purpose, model=model, language=lang)
		params = ttsstyles.style_params(purpose)
		audio = self._cli.text_to_speech(
			text, language_code=lang, speaker=voice, model=model,
			pace=params["pace"], temperature=params["temperature"],
			sample_rate=self._conf.get("sampleRate"), output_audio_codec=fmt,
			cancel=self._cancel)
		path = self._unique(safe_file_name(file_name, "." + fmt))
		with open(path, "wb") as f:
			f.write(audio)
		self.saved_files.append(path)
		res = {"saved": os.path.basename(path), "voice": ttsstyles.voice_label(voice),
			"language": constants.language_name(lang)}
		if self._cli.last_tts_note:
			res["note"] = self._cli.last_tts_note
		return res

	def tool_save_document(self, content, file_name, format="docx"):
		fmt = format if format in exporter.format_keys(include_tables=True) else "docx"
		path = self._unique(safe_file_name(file_name, exporter.extension(fmt)))
		exporter.export(content, path, fmt, title=os.path.splitext(os.path.basename(path))[0])
		self.saved_files.append(path)
		return {"saved": os.path.basename(path), "format": fmt}

	def tool_get_current_date_time(self):
		return {"local": time.strftime("%A %d %B %Y, %H:%M")}


def describe_call(name, args):
	"""A short, speakable description of a tool call for the step log."""
	a = args or {}
	if name == "read_attached_file":
		return _("Reading attached file {n}").format(n=a.get("index"))
	if name == "list_attached_files":
		return _("Looking at the attached files")
	if name == "translate_text":
		return _("Translating to {lang}").format(lang=constants.language_name(a.get("target_language", "")))
	if name == "transliterate_text":
		return _("Transliterating to {lang}").format(lang=constants.language_name(a.get("target_language", "")))
	if name == "detect_language":
		return _("Detecting the language")
	if name == "create_speech_file":
		return _("Creating speech file {name}").format(name=a.get("file_name", ""))
	if name == "save_document":
		return _("Saving {name} as {fmt}").format(name=a.get("file_name", ""), fmt=a.get("format", ""))
	if name == "get_current_date_time":
		return _("Checking the date and time")
	return name


def run_agent(client, messages, model, tools_impl, effort=None, max_steps=8,
		max_tokens=None, on_step=None, cancel=None):
	"""Run the tool loop until the model answers without calling a tool.

	``messages`` is updated in place (so a conversation can continue).
	``on_step(text)`` is called (from the worker thread) for every step.
	Returns the final answer text.
	"""
	for step in range(max(1, int(max_steps))):
		if cancel:
			cancel.check()
		msg = client.chat_message(
			messages, model=model, reasoning_effort=effort, tools=list(TOOLS),
			max_tokens=max_tokens, cancel=cancel)
		calls = msg.get("tool_calls") or []
		assistant = {"role": "assistant", "content": msg.get("content") or ""}
		if calls:
			assistant["tool_calls"] = calls
		messages.append(assistant)
		if not calls:
			return msg.get("content") or ""
		for call in calls:
			fn = (call.get("function") or {})
			name = fn.get("name", "")
			try:
				args = json.loads(fn.get("arguments") or "{}")
			except ValueError:
				args = {}
			if on_step:
				on_step(describe_call(name, args))
			result = tools_impl.run(name, args)
			if on_step and isinstance(result, dict):
				if result.get("error"):
					on_step(_("  Problem: {err}").format(err=result["error"]))
				elif result.get("saved"):
					on_step(_("  Saved {name}").format(name=result["saved"]))
			messages.append({
				"role": "tool",
				"tool_call_id": call.get("id") or name,
				"content": json.dumps(result, ensure_ascii=False)[:_READ_LIMIT + 2000],
			})
	# Out of steps: ask for a final answer without tools.
	if on_step:
		on_step(_("Step limit reached; asking for a final summary."))
	messages.append({"role": "user", "content":
		"Stop calling tools now and summarise what was done and what is left."})
	msg = client.chat_message(messages, model=model, reasoning_effort=effort,
		max_tokens=max_tokens, cancel=cancel)
	messages.append({"role": "assistant", "content": msg.get("content") or ""})
	return msg.get("content") or ""


SCHEMA_PROMPT = (
	"Convert the user's description of the data they want from a document into "
	"a JSON Schema for Sarvam Document AI extraction. Rules: the root is "
	'{"type":"object","properties":{...}}; allowed types are string, number, '
	"integer, boolean, object and array; nest at most 4 levels; every property "
	"must have a short description; repeated rows (like line items or table "
	"rows) are an array of objects. Property names use snake_case. Reply with "
	"the JSON schema only.")


def build_extract_schema(client, description, model=None, cancel=None):
	"""Agentic step for Document AI extract: plain words -> JSON schema."""
	model = model or models.DEFAULT_CHAT_MODEL
	messages = [
		{"role": "system", "content": SCHEMA_PROMPT},
		{"role": "user", "content": description},
	]
	text = client.chat(messages, model=model, reasoning_effort=models.normalise_effort(model, "low"),
		response_format={"type": "json_object"}, cancel=cancel)
	return parse_schema(text)


def parse_schema(text):
	m = re.search(r"\{.*\}", text or "", re.DOTALL)
	if not m:
		raise errors.SarvamError(_("Could not build a data schema from your description."))
	try:
		schema = json.loads(m.group(0))
	except ValueError:
		raise errors.SarvamError(_("Could not build a data schema from your description."))
	if "properties" not in schema and isinstance(schema, dict):
		schema = {"type": "object", "properties": schema}
	schema["type"] = "object"
	if not schema.get("properties"):
		raise errors.SarvamError(_("Could not build a data schema from your description."))
	return schema


def extract_result_to_markdown(data):
	"""Render a Document AI extract result as Markdown (tables for lists)."""
	if not isinstance(data, dict):
		return json.dumps(data, ensure_ascii=False, indent=2)
	lines = []
	simple = [(k, v) for k, v in data.items() if not isinstance(v, (list, dict))]
	if simple:
		lines.append("| Field | Value |")
		lines.append("|---|---|")
		for k, v in simple:
			lines.append("| %s | %s |" % (k.replace("_", " "), str(v).replace("|", "/")))
		lines.append("")
	for k, v in data.items():
		if isinstance(v, list) and v and all(isinstance(r, dict) for r in v):
			cols = []
			for r in v:
				for c in r:
					if c not in cols:
						cols.append(c)
			lines.append("## " + k.replace("_", " ").capitalize())
			lines.append("")
			lines.append("| " + " | ".join(c.replace("_", " ") for c in cols) + " |")
			lines.append("|" + "---|" * len(cols))
			for r in v:
				lines.append("| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in cols) + " |")
			lines.append("")
		elif isinstance(v, (list, dict)):
			lines.append("## " + k.replace("_", " ").capitalize())
			lines.append("")
			lines.append(json.dumps(v, ensure_ascii=False, indent=2))
			lines.append("")
	return "\n".join(lines).strip()
