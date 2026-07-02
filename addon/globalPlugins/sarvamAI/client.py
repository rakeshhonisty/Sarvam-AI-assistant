# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""The single, isolated Sarvam AI HTTP client.

Design goals:

* **No third-party dependencies.** NVDA does not bundle ``requests``, so all
  HTTP is done with the standard library (:mod:`urllib`). This keeps the
  packaged add-on self-contained.
* **One place for the wire format.** Every endpoint, header and parameter name
  lives here or in :mod:`constants`, so adapting to Sarvam API changes touches
  a single module.
* **Screen-reader friendly failures.** All errors are converted to
  :class:`~.errors.SarvamError` subclasses with human messages.
* **Cancellable & timeout-bounded**, so the UI never blocks NVDA.
"""

import json
import os
import ssl
import time
import base64
import urllib.request
import urllib.error

import addonHandler

from . import constants
from . import errors
from . import logger

addonHandler.initTranslation()

_USER_AGENT = "SarvamAI-NVDA-Addon/1.0 (+https://github.com/)"


def _multipart_encode(fields, files):
	"""Encode ``fields`` (dict of str) and ``files`` (list of
	(name, filename, bytes, content_type)) as multipart/form-data.

	Returns ``(content_type_header, body_bytes)``.
	"""
	boundary = "----SarvamAINVDA" + os.urandom(16).hex()
	crlf = b"\r\n"
	buf = []
	for name, value in (fields or {}).items():
		if value is None:
			continue
		buf.append(b"--" + boundary.encode("ascii"))
		buf.append(('Content-Disposition: form-data; name="%s"' % name).encode("utf-8"))
		buf.append(b"")
		buf.append(str(value).encode("utf-8"))
	for name, filename, data, ctype in (files or []):
		buf.append(b"--" + boundary.encode("ascii"))
		buf.append((
			'Content-Disposition: form-data; name="%s"; filename="%s"'
			% (name, filename)).encode("utf-8"))
		buf.append(("Content-Type: %s" % (ctype or "application/octet-stream")).encode("ascii"))
		buf.append(b"")
		buf.append(data)
	buf.append(b"--" + boundary.encode("ascii") + b"--")
	buf.append(b"")
	body = crlf.join(buf)
	return "multipart/form-data; boundary=%s" % boundary, body


def _guess_audio_ctype(path):
	ext = os.path.splitext(path)[1].lower()
	return {
		".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
		".aac": "audio/aac", ".flac": "audio/flac", ".ogg": "audio/ogg",
		".opus": "audio/opus", ".webm": "audio/webm",
	}.get(ext, "application/octet-stream")


class CancelToken:
	"""A tiny cooperative cancellation flag shared with worker threads."""

	def __init__(self):
		self._cancelled = False

	def cancel(self):
		self._cancelled = True

	@property
	def cancelled(self):
		return self._cancelled

	def check(self):
		if self._cancelled:
			raise errors.CancelledError(_("Operation cancelled."))


class SarvamClient:
	"""Thin wrapper over the Sarvam REST API.

	The client reads its configuration (key, base URL, timeout, retries, proxy)
	lazily through the ``config`` module so that changes in the settings panel
	take effect immediately without recreating the object.
	"""

	def __init__(self, config_module):
		self._cfg = config_module

	# -- low level ----------------------------------------------------------
	def _key(self):
		key = self._cfg.getApiKey()
		if not key:
			raise errors.AuthenticationError(
				_("No Sarvam API key set. Open Sarvam AI settings and enter your key."))
		return key

	def _base(self):
		return (self._cfg.conf().get("baseUrl") or constants.DEFAULT_BASE_URL).rstrip("/")

	def _timeout(self):
		try:
			return max(5, int(self._cfg.conf().get("networkTimeout", 60)))
		except Exception:
			return 60

	def _retries(self):
		try:
			return max(0, int(self._cfg.conf().get("maxRetries", 2)))
		except Exception:
			return 2

	def _opener(self):
		handlers = []
		proxy = (self._cfg.conf().get("proxyUrl") or "").strip()
		if proxy:
			handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
		else:
			# Respect system proxy settings when no explicit proxy is set.
			handlers.append(urllib.request.ProxyHandler())
		ctx = ssl.create_default_context()
		handlers.append(urllib.request.HTTPSHandler(context=ctx))
		return urllib.request.build_opener(*handlers)

	def _request(self, method, path, headers=None, data=None, cancel=None, expect_json=True):
		"""Perform one HTTP request with retry/backoff and error mapping."""
		url = self._base() + path
		hdrs = {
			constants.AUTH_HEADER: self._key(),
			"User-Agent": _USER_AGENT,
			"Accept": "application/json",
		}
		if headers:
			hdrs.update(headers)
		attempts = self._retries() + 1
		last_err = None
		for attempt in range(attempts):
			if cancel:
				cancel.check()
			try:
				logger.debug("%s %s (attempt %d/%d)" % (method, path, attempt + 1, attempts))
				req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
				with self._opener().open(req, timeout=self._timeout()) as resp:
					raw = resp.read()
				if not expect_json:
					return raw
				return json.loads(raw.decode("utf-8")) if raw else {}
			except urllib.error.HTTPError as e:
				body = b""
				try:
					body = e.read()
				except Exception:
					pass
				payload = _safe_json(body)
				err = errors.error_from_status(e.code, payload)
				logger.warning("HTTP %s on %s: %s" % (e.code, path, err.message))
				if err.retryable and attempt < attempts - 1:
					last_err = err
					_backoff(attempt, getattr(err, "retry_after", None))
					continue
				raise err
			except errors.CancelledError:
				raise
			except (urllib.error.URLError, ssl.SSLError, OSError) as e:
				reason = getattr(e, "reason", e)
				err = errors.NetworkError(
					_("Could not reach Sarvam. Check your internet connection. ({reason})").format(reason=reason))
				logger.warning("Network error on %s: %s" % (path, reason))
				if attempt < attempts - 1:
					last_err = err
					_backoff(attempt, None)
					continue
				raise err
			except ValueError as e:
				raise errors.SarvamError(
					_("Received an unexpected response from Sarvam. ({err})").format(err=e))
		if last_err:
			raise last_err
		raise errors.SarvamError(_("Request failed for an unknown reason."))

	def _post_json(self, path, payload, cancel=None):
		data = json.dumps(payload).encode("utf-8")
		return self._request(
			"POST", path, headers={"Content-Type": "application/json"},
			data=data, cancel=cancel)

	def _post_multipart(self, path, fields, files, cancel=None):
		ctype, body = _multipart_encode(fields, files)
		return self._request(
			"POST", path, headers={"Content-Type": ctype}, data=body, cancel=cancel)

	# -- diagnostics --------------------------------------------------------
	def list_models(self, cancel=None):
		"""GET /v1/models. Also serves as a lightweight auth/connectivity test."""
		res = self._request("GET", constants.EP_MODELS, cancel=cancel)
		data = res.get("data") if isinstance(res, dict) else None
		return [m.get("id") for m in (data or []) if isinstance(m, dict)]

	def test_connection(self, cancel=None):
		"""Validate the key and connectivity. Returns a status string."""
		models = self.list_models(cancel=cancel)
		return _("Connection OK. {n} models available: {models}").format(
			n=len(models), models=", ".join(models) or _("none"))

	# -- text to speech -----------------------------------------------------
	def text_to_speech(self, text, language_code, speaker=None, model=None,
			pitch=None, pace=None, loudness=None, sample_rate=None,
			enable_preprocessing=True, temperature=None, output_audio_codec=None,
			cancel=None, progress=None):
		"""Synthesise ``text`` and return the raw audio bytes in the requested
		codec (``wav`` for playback, ``mp3`` etc. for saving).

		Long input is split into <= ``TTS_MAX_CHARS`` chunks; the resulting audio
		segments are joined (WAV segments are re-framed into one valid WAV, other
		codecs are concatenated).
		"""
		codec = (output_audio_codec or "wav").lower()
		chunks = _chunk_text(text, constants.TTS_MAX_CHARS)
		segments = []
		total = len(chunks)
		for i, chunk in enumerate(chunks):
			if cancel:
				cancel.check()
			if progress:
				progress(i, total)
			payload = {
				"text": chunk,
				"target_language_code": language_code,
				"speaker": speaker or constants.DEFAULT_SPEAKER,
				"model": model or constants.DEFAULT_TTS_MODEL,
				"enable_preprocessing": bool(enable_preprocessing),
				"output_audio_codec": codec,
			}
			if pitch is not None:
				payload["pitch"] = float(pitch)
			if pace is not None:
				payload["pace"] = float(pace)
			if loudness is not None:
				payload["loudness"] = float(loudness)
			if temperature is not None:
				payload["temperature"] = float(temperature)
			if sample_rate:
				payload["speech_sample_rate"] = int(sample_rate)
			res = self._post_json(constants.EP_TEXT_TO_SPEECH, payload, cancel=cancel)
			audios = res.get("audios") if isinstance(res, dict) else None
			if not audios:
				raise errors.SarvamError(_("Sarvam did not return any audio."))
			segments.append(base64.b64decode(audios[0]))
		if progress:
			progress(total, total)
		if codec == "wav":
			return _concat_wav(segments)
		return b"".join(segments)

	# -- speech to text -----------------------------------------------------
	def speech_to_text(self, audio_path, language_code=None, model=None,
			with_timestamps=False, cancel=None):
		"""Transcribe an audio file. Returns a dict with ``transcript`` and
		``language_code``."""
		with open(audio_path, "rb") as f:
			data = f.read()
		fields = {"model": model or constants.DEFAULT_STT_MODEL}
		if language_code:
			fields["language_code"] = language_code
		if with_timestamps:
			fields["with_timestamps"] = "true"
		files = [("file", os.path.basename(audio_path), data, _guess_audio_ctype(audio_path))]
		res = self._post_multipart(constants.EP_SPEECH_TO_TEXT, fields, files, cancel=cancel)
		return _normalise_transcript(res)

	def speech_to_text_translate(self, audio_path, model=None, prompt=None, cancel=None):
		"""Transcribe an audio file and translate to English."""
		with open(audio_path, "rb") as f:
			data = f.read()
		fields = {"model": model or constants.DEFAULT_STT_TRANSLATE_MODEL}
		if prompt:
			fields["prompt"] = prompt
		files = [("file", os.path.basename(audio_path), data, _guess_audio_ctype(audio_path))]
		res = self._post_multipart(constants.EP_SPEECH_TO_TEXT_TRANSLATE, fields, files, cancel=cancel)
		return _normalise_transcript(res)

	# -- translation & language --------------------------------------------
	def translate(self, text, source_language_code, target_language_code,
			model=None, mode=None, speaker_gender=None, output_script=None,
			numerals_format=None, enable_preprocessing=False, cancel=None):
		payload = {
			"input": text,
			"source_language_code": source_language_code or constants.AUTO_DETECT,
			"target_language_code": target_language_code,
			"model": model or constants.DEFAULT_TRANSLATE_MODEL,
			"enable_preprocessing": bool(enable_preprocessing),
		}
		if mode:
			payload["mode"] = mode
		if speaker_gender:
			payload["speaker_gender"] = speaker_gender
		if output_script:
			payload["output_script"] = output_script
		if numerals_format:
			payload["numerals_format"] = numerals_format
		res = self._post_json(constants.EP_TRANSLATE, payload, cancel=cancel)
		return {
			"translated_text": res.get("translated_text", ""),
			"source_language_code": res.get("source_language_code", source_language_code),
			"request_id": res.get("request_id"),
		}

	def transliterate(self, text, source_language_code, target_language_code,
			numerals_format=None, spoken_form=False, cancel=None):
		payload = {
			"input": text,
			"source_language_code": source_language_code or constants.AUTO_DETECT,
			"target_language_code": target_language_code,
		}
		if numerals_format:
			payload["numerals_format"] = numerals_format
		if spoken_form:
			payload["spoken_form"] = True
		res = self._post_json(constants.EP_TRANSLITERATE, payload, cancel=cancel)
		return {
			"transliterated_text": res.get("transliterated_text", ""),
			"source_language_code": res.get("source_language_code", source_language_code),
		}

	def detect_language(self, text, cancel=None):
		"""POST /text-lid. Returns dict with ``language_code`` and ``script_code``."""
		res = self._post_json(constants.EP_TEXT_LID, {"input": text}, cancel=cancel)
		return {
			"language_code": res.get("language_code"),
			"script_code": res.get("script_code"),
		}

	# -- chat / summarise ---------------------------------------------------
	def chat(self, messages, model=None, temperature=None, max_tokens=None,
			cancel=None):
		"""OpenAI-compatible /v1/chat/completions. ``messages`` is a list of
		``{"role": ..., "content": str}`` dicts. Returns the assistant text."""
		payload = {
			"model": model or constants.DEFAULT_CHAT_MODEL,
			"messages": messages,
		}
		if temperature is not None:
			payload["temperature"] = float(temperature)
		if max_tokens:
			payload["max_tokens"] = int(max_tokens)
		res = self._post_json(constants.EP_CHAT_COMPLETIONS, payload, cancel=cancel)
		try:
			return res["choices"][0]["message"]["content"]
		except (KeyError, IndexError, TypeError):
			raise errors.SarvamError(_("Sarvam returned an empty chat response."))

	def summarize(self, text, instruction=None, model=None, cancel=None):
		instruction = instruction or _("Summarise the following text clearly and concisely.")
		messages = [
			{"role": "system", "content": instruction},
			{"role": "user", "content": text},
		]
		return self.chat(messages, model=model, cancel=cancel)

	# -- document OCR (Sarvam document digitization) ------------------------
	def _put_url(self, url, data, storage_type=None):
		"""Upload ``data`` to a presigned URL with a raw PUT (no auth header)."""
		headers = {"User-Agent": _USER_AGENT, "Content-Type": "application/octet-stream"}
		# Azure Block Blob presigned PUTs require this header.
		if storage_type and str(storage_type).lower().startswith("azure"):
			headers["x-ms-blob-type"] = "BlockBlob"
		req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
		try:
			with self._opener().open(req, timeout=self._timeout()) as resp:
				resp.read()
		except urllib.error.HTTPError as e:
			body = b""
			try:
				body = e.read()
			except Exception:
				pass
			raise errors.SarvamError(
				_("Uploading the document failed (HTTP {code}). {body}").format(
					code=e.code, body=body.decode("utf-8", "replace")[:200]))
		except (urllib.error.URLError, OSError) as e:
			raise errors.NetworkError(
				_("Could not upload the document: {err}").format(err=getattr(e, "reason", e)))

	def _get_url(self, url):
		"""Download bytes from a presigned URL with a raw GET (no auth header)."""
		req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}, method="GET")
		try:
			with self._opener().open(req, timeout=self._timeout()) as resp:
				return resp.read()
		except urllib.error.HTTPError as e:
			raise errors.SarvamError(
				_("Downloading the OCR result failed (HTTP {code}).").format(code=e.code))
		except (urllib.error.URLError, OSError) as e:
			raise errors.NetworkError(
				_("Could not download the OCR result: {err}").format(err=getattr(e, "reason", e)))

	def document_ocr(self, pdf_path, language=None, output_format=None,
			cancel=None, progress=None, poll_interval=3.0, max_wait=600):
		"""Run Sarvam document OCR on a single PDF and return the extracted text.

		Implements the full job lifecycle: create -> get upload URL -> upload ->
		start -> poll status -> get download URL -> download ZIP -> extract text.
		"""
		language = language or constants.DEFAULT_OCR_LANGUAGE
		output_format = output_format or constants.DEFAULT_OCR_OUTPUT_FORMAT
		filename = os.path.basename(pdf_path)

		def step(msg, i, n):
			logger.debug("OCR: %s" % msg)
			if progress:
				progress(i, n)

		# 1) Create job.
		step("create job", 0, 6)
		created = self._post_json(constants.EP_OCR_CREATE, {
			"job_parameters": {"language": language, "output_format": output_format}
		}, cancel=cancel)
		job_id = created.get("job_id")
		storage = created.get("storage_container_type")
		if not job_id:
			raise errors.SarvamError(_("Sarvam did not return an OCR job id."))

		# 2) Get upload URL.
		step("request upload url", 1, 6)
		up = self._post_json(constants.EP_OCR_UPLOAD, {
			"job_id": job_id, "files": [filename]
		}, cancel=cancel)
		upload_urls = up.get("upload_urls") or {}
		details = upload_urls.get(filename) or (list(upload_urls.values())[0] if upload_urls else None)
		if not details or not details.get("file_url"):
			raise errors.SarvamError(_("Sarvam did not return an upload URL."))

		# 3) Upload the PDF bytes to the presigned URL.
		step("upload document", 2, 6)
		with open(pdf_path, "rb") as f:
			self._put_url(details["file_url"], f.read(), storage_type=storage)

		# 4) Start the job.
		if cancel:
			cancel.check()
		step("start job", 3, 6)
		self._request("POST", constants.EP_OCR_START.format(job_id=job_id), cancel=cancel)

		# 5) Poll for completion.
		step("processing", 4, 6)
		waited = 0.0
		state = None
		while waited < max_wait:
			if cancel:
				cancel.check()
			status = self._request("GET", constants.EP_OCR_STATUS.format(job_id=job_id), cancel=cancel)
			state = status.get("job_state")
			logger.debug("OCR job %s state=%s" % (job_id, state))
			if state in constants.OCR_TERMINAL_STATES:
				if state == "Failed":
					raise errors.SarvamError(
						_("OCR failed: {msg}").format(msg=status.get("error_message") or state))
				break
			time.sleep(poll_interval)
			waited += poll_interval
		else:
			raise errors.SarvamError(_("OCR timed out. Please try again."))

		# 6) Get download URL(s) and fetch the result ZIP.
		step("download result", 5, 6)
		dl = self._request("POST", constants.EP_OCR_DOWNLOAD.format(job_id=job_id), cancel=cancel)
		download_urls = dl.get("download_urls") or {}
		if not download_urls:
			raise errors.SarvamError(_("Sarvam returned no OCR output. The document may be empty."))
		texts = []
		for name, det in download_urls.items():
			url = det.get("file_url") if isinstance(det, dict) else None
			if not url:
				continue
			blob = self._get_url(url)
			texts.append(_extract_ocr_text(name, blob, output_format))
		step("done", 6, 6)
		text = "\n\n".join(t for t in texts if t).strip()
		if not text:
			raise errors.SarvamError(_("No text could be extracted from the document."))
		return {"text": text, "job_id": job_id, "state": state, "format": output_format}


# --- module-level helpers ---------------------------------------------------
def _safe_json(body):
	try:
		return json.loads(body.decode("utf-8"))
	except Exception:
		try:
			return body.decode("utf-8", "replace")
		except Exception:
			return ""


def _backoff(attempt, retry_after):
	delay = float(retry_after) if retry_after else min(8.0, 0.5 * (2 ** attempt))
	time.sleep(delay)


def _chunk_text(text, limit):
	text = (text or "").strip()
	if not text:
		raise errors.InvalidRequestError(_("There is no text to synthesise."))
	if len(text) <= limit:
		return [text]
	chunks = []
	current = ""
	# Prefer splitting on sentence boundaries, then whitespace.
	import re
	parts = re.split(r"(?<=[.!?।])\s+", text)
	for part in parts:
		while len(part) > limit:
			chunks.append(part[:limit])
			part = part[limit:]
		if len(current) + len(part) + 1 <= limit:
			current = (current + " " + part).strip()
		else:
			if current:
				chunks.append(current)
			current = part
	if current:
		chunks.append(current)
	return chunks


def _normalise_transcript(res):
	if not isinstance(res, dict):
		return {"transcript": str(res), "language_code": None}
	return {
		"transcript": res.get("transcript", res.get("text", "")),
		"language_code": res.get("language_code") or res.get("detected_language_code"),
		"request_id": res.get("request_id"),
		"diarized_transcript": res.get("diarized_transcript"),
	}


def _extract_ocr_text(name, blob, output_format):
	"""Turn an OCR result payload (a ZIP of md/html/json, or a single file)
	into plain, readable text."""
	import io
	import zipfile

	def to_text(fname, data):
		try:
			raw = data.decode("utf-8", "replace")
		except Exception:
			return ""
		low = fname.lower()
		if low.endswith(".json") or output_format == "json":
			return _json_to_text(raw)
		if low.endswith((".html", ".htm")) or output_format == "html":
			return _strip_html(raw)
		return raw  # markdown / plain

	# ZIP archive?
	if blob[:2] == b"PK":
		parts = []
		try:
			with zipfile.ZipFile(io.BytesIO(blob)) as zf:
				for info in sorted(zf.namelist()):
					if info.endswith("/"):
						continue
					parts.append(to_text(info, zf.read(info)))
		except zipfile.BadZipFile:
			return blob.decode("utf-8", "replace")
		return "\n\n".join(p for p in parts if p and p.strip())
	return to_text(name, blob)


def _json_to_text(raw):
	try:
		data = json.loads(raw)
	except Exception:
		return raw
	chunks = []

	def walk(node):
		if isinstance(node, dict):
			for key in ("text", "content", "markdown", "value"):
				val = node.get(key)
				if isinstance(val, str) and val.strip():
					chunks.append(val)
			for v in node.values():
				walk(v)
		elif isinstance(node, list):
			for v in node:
				walk(v)

	walk(data)
	return "\n".join(chunks) if chunks else raw


def _strip_html(raw):
	import re
	text = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
	text = re.sub(r"(?s)<[^>]+>", " ", text)
	text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
		.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
	text = re.sub(r"[ \t]+", " ", text)
	text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
	return text.strip()


def _concat_wav(wavs):
	"""Concatenate a list of WAV byte strings into a single WAV.

	Uses the :mod:`wave` module so the output has a correct header. Falls back
	to returning the first segment if parsing fails.
	"""
	if len(wavs) == 1:
		return wavs[0]
	import io
	import wave
	try:
		params = None
		frames = []
		for w in wavs:
			with wave.open(io.BytesIO(w), "rb") as wf:
				if params is None:
					params = wf.getparams()
				frames.append(wf.readframes(wf.getnframes()))
		out = io.BytesIO()
		with wave.open(out, "wb") as wf:
			wf.setparams(params)
			for fr in frames:
				wf.writeframes(fr)
		return out.getvalue()
	except Exception:
		logger.warning("Could not concatenate WAV chunks; returning first segment.")
		return wavs[0]
