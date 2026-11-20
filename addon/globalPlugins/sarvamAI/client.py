# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""The single, isolated Sarvam AI HTTP client.

Design goals:

* **No third-party dependencies.** NVDA does not bundle ``requests``, so all
  HTTP is done with the standard library (:mod:`urllib`).
* **One place for the wire format.** Every endpoint, header and parameter name
  lives here or in :mod:`constants` / :mod:`models`.
* **Screen-reader friendly failures.** All errors are converted to
  :class:`~.errors.SarvamError` subclasses with human messages.
* **Cancellable & timeout-bounded**, so the UI never blocks NVDA.
* **Graceful fallbacks** where Sarvam has both a current and a legacy API
  (Document AI -> legacy digitization, chat V2 -> V1 for Sarvam 105B,
  bulbul:v4-flash -> bulbul:v3 for languages v4 does not cover).
"""

import json
import os
import ssl
import time
import base64
import urllib.parse
import urllib.request
import urllib.error

import addonHandler

from . import constants
from . import errors
from . import logger
from . import models
from . import ttsstyles

addonHandler.initTranslation()

_USER_AGENT = "SarvamAI-NVDA-Addon/2.0 (+https://github.com/rakeshhonisty/Sarvam-AI-assistant)"

# MIME types for uploads.
_MIME = {
	".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
	".aac": "audio/aac", ".aiff": "audio/aiff", ".aif": "audio/aiff",
	".flac": "audio/flac", ".ogg": "audio/ogg", ".opus": "audio/opus",
	".webm": "audio/webm", ".amr": "audio/amr", ".wma": "audio/x-ms-wma",
	".pdf": "application/pdf", ".zip": "application/zip",
	".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
	".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
	".webp": "image/webp",
	".doc": "application/msword",
	".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	".odt": "application/vnd.oasis.opendocument.text",
	".xls": "application/vnd.ms-excel",
	".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	".ods": "application/vnd.oasis.opendocument.spreadsheet",
	".ppt": "application/vnd.ms-powerpoint",
	".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
	".odp": "application/vnd.oasis.opendocument.presentation",
	".html": "text/html", ".htm": "text/html", ".xhtml": "application/xhtml+xml",
	".mhtml": "multipart/related", ".md": "text/markdown", ".markdown": "text/markdown",
	".txt": "text/plain",
}


def mime_type(path):
	return _MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


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
		safe_name = filename.replace('"', "'")
		buf.append(b"--" + boundary.encode("ascii"))
		buf.append((
			'Content-Disposition: form-data; name="%s"; filename="%s"'
			% (name, safe_name)).encode("utf-8"))
		buf.append(("Content-Type: %s" % (ctype or "application/octet-stream")).encode("ascii"))
		buf.append(b"")
		buf.append(data)
	buf.append(b"--" + boundary.encode("ascii") + b"--")
	buf.append(b"")
	body = crlf.join(buf)
	return "multipart/form-data; boundary=%s" % boundary, body


def _guess_audio_ctype(path):
	return mime_type(path)


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


def _sleep(seconds, cancel=None):
	"""Sleep in small slices so a cancel request is honoured quickly."""
	end = time.time() + seconds
	while time.time() < end:
		if cancel:
			cancel.check()
		time.sleep(min(0.25, max(0.0, end - time.time())))


class SarvamClient:
	"""Thin wrapper over the Sarvam REST API.

	The client reads its configuration (key, base URL, timeout, retries, proxy)
	lazily through the ``config`` module so that changes in the settings panel
	take effect immediately without recreating the object.
	"""

	def __init__(self, config_module):
		self._cfg = config_module
		#: Set by text_to_speech when it had to switch model or voice.
		self.last_tts_note = None

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
			return max(5, int(self._cfg.conf().get("networkTimeout", 120)))
		except Exception:
			return 120

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
			handlers.append(urllib.request.ProxyHandler())
		ctx = ssl.create_default_context()
		handlers.append(urllib.request.HTTPSHandler(context=ctx))
		return urllib.request.build_opener(*handlers)

	def _request(self, method, path, headers=None, data=None, cancel=None, expect_json=True):
		"""Perform one HTTP request with retry/backoff and error mapping."""
		url = path if path.startswith("http") else self._base() + path
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

	def _post_json(self, path, payload, cancel=None, headers=None):
		data = json.dumps(payload).encode("utf-8")
		hdrs = {"Content-Type": "application/json"}
		if headers:
			hdrs.update(headers)
		return self._request("POST", path, headers=hdrs, data=data, cancel=cancel)

	def _post_multipart(self, path, fields, files, cancel=None):
		ctype, body = _multipart_encode(fields, files)
		return self._request(
			"POST", path, headers={"Content-Type": ctype}, data=body, cancel=cancel)

	# -- diagnostics --------------------------------------------------------
	def list_models(self, cancel=None):
		"""GET /v2/models (falls back to /v1/models). Returns model ids."""
		try:
			res = self._request("GET", constants.EP_MODELS, cancel=cancel)
		except errors.InvalidRequestError:
			res = self._request("GET", constants.EP_MODELS_V1, cancel=cancel)
		data = res.get("data") if isinstance(res, dict) else None
		return [m.get("id") for m in (data or []) if isinstance(m, dict) and m.get("id")]

	def test_connection(self, cancel=None):
		"""Validate the key and connectivity. Returns a status string."""
		ids = self.list_models(cancel=cancel)
		return _("Connection OK. {n} chat models available to your key: {models}").format(
			n=len(ids), models=", ".join(ids) or _("none"))

	# -- text to speech -----------------------------------------------------
	def text_to_speech(self, text, language_code, speaker=None, model=None,
			pitch=None, pace=None, loudness=None, sample_rate=None,
			enable_preprocessing=None, temperature=None, output_audio_codec=None,
			cancel=None, progress=None, concurrency=1):
		"""Synthesise ``text`` and return the raw audio bytes in the requested
		codec (``wav`` for playback, ``mp3``/``flac``/``aac`` for saving).

		Long input is split into <= 2500 character chunks (optionally several
		synthesised at once); WAV segments are re-framed into one valid WAV,
		other codecs are concatenated.

		bulbul:v4-flash does not cover Malayalam or Odia. For those the request
		automatically switches to bulbul:v3 with the closest matching voice of
		the same gender and purpose, and ``self.last_tts_note`` explains it.
		"""
		self.last_tts_note = None
		model = model or models.DEFAULT_TTS_MODEL
		speaker = speaker or (ttsstyles.V4_DEFAULT_SPEAKER if model == ttsstyles.MODEL_V4
			else ttsstyles.V3_DEFAULT_SPEAKER)
		# A voice belongs to exactly one model; keep the pair consistent.
		if ttsstyles.model_of(speaker) != model:
			model = ttsstyles.model_of(speaker)
		if model == ttsstyles.MODEL_V4 and not models.tts_supports_language(model, language_code):
			purposes = ttsstyles.purposes_of(speaker)
			new_speaker = ttsstyles.best_v3_voice(
				ttsstyles.gender_of(speaker), purposes[0] if purposes else None)
			self.last_tts_note = _(
				"Bulbul v4 Flash does not support {lang}, so Bulbul v3 voice {voice} was used.").format(
				lang=constants.language_name(language_code), voice=new_speaker.capitalize())
			logger.info(self.last_tts_note)
			model, speaker = ttsstyles.MODEL_V3, new_speaker
		codec = (output_audio_codec or "wav").lower()
		chunks = _chunk_text(text, models.tts_info(model)["max_chars"])
		total = len(chunks)
		done = [0]
		if progress:
			progress(0, total)

		def one(chunk):
			if cancel:
				cancel.check()
			payload = {
				"text": chunk,
				"target_language_code": language_code,
				"speaker": speaker,
				"model": model,
				"output_audio_codec": codec,
			}
			# bulbul:v3/v4-flash support only pace and temperature; pitch,
			# loudness and enable_preprocessing are v2-only and are never sent.
			if pace is not None:
				payload["pace"] = ttsstyles.clamp_pace(pace)
			if temperature is not None:
				payload["temperature"] = ttsstyles.clamp_temperature(temperature)
			if sample_rate:
				payload["speech_sample_rate"] = int(sample_rate)
			res = self._post_json(constants.EP_TEXT_TO_SPEECH, payload, cancel=cancel)
			audios = res.get("audios") if isinstance(res, dict) else None
			if not audios:
				raise errors.SarvamError(_("Sarvam did not return any audio."))
			done[0] += 1
			if progress:
				progress(done[0], total)
			return base64.b64decode(audios[0])

		if total == 1:
			segments = [one(chunks[0])]
		else:
			from . import tasks as _tasks
			segments = _tasks.parallel_map(one, chunks, concurrency=concurrency, cancel=cancel)
		if codec == "wav":
			return _concat_wav(segments)
		return b"".join(segments)

	# -- speech to text -----------------------------------------------------
	def speech_to_text(self, audio_path, language_code=None, model=None,
			with_timestamps=False, mode=None, keyterms=None, cancel=None):
		"""Real-time transcription of a short clip (up to 30 seconds).

		``mode`` selects the output form (transcribe, translate, verbatim,
		translit, codemix). ``keyterms`` (saaras:v4 only) is a list of names
		or terms to spell correctly. ``language_code`` "unknown" lets Sarvam
		detect the language, which also allows mixed-language speech.
		"""
		with open(audio_path, "rb") as f:
			data = f.read()
		model = model or models.DEFAULT_STT_MODEL
		fields = {
			"model": model,
			"language_code": language_code or constants.STT_AUTO_LANGUAGE,
		}
		if mode:
			fields["mode"] = mode
		if with_timestamps:
			fields["with_timestamps"] = "true"
		terms = _clean_keyterms(keyterms)
		if terms and models.stt_supports_keyterms(model):
			fields["keyterms"] = json.dumps(terms, ensure_ascii=False)
		files = [("file", os.path.basename(audio_path), data, _guess_audio_ctype(audio_path))]
		res = self._post_multipart(constants.EP_SPEECH_TO_TEXT, fields, files, cancel=cancel)
		return _normalise_transcript(res)

	def speech_to_text_translate(self, audio_path, model=None, prompt=None, cancel=None):
		"""Transcribe and translate to English.

		The legacy /speech-to-text-translate endpoint (saaras:v2.5) is retired
		in 2.0; this now uses /speech-to-text with ``mode="translate"``.
		"""
		return self.speech_to_text(audio_path, model=model, mode="translate", cancel=cancel)

	def transcribe(self, audio_path, language_code=None, model=None,
			translate=False, mode=None, keyterms=None, with_timestamps=False,
			diarization=False, num_speakers=None, cancel=None, progress=None):
		"""Transcribe audio of any length.

		Short clips use the real-time API; long audio, or any request for
		speaker separation (diarization), uses the batch job API. If the
		real-time API rejects a clip as too long it is retried as a batch job
		automatically. Returns a dict with ``transcript`` (and, when requested,
		``segments`` with timings and speakers).
		"""
		if translate:
			mode = "translate"
		try:
			size = os.path.getsize(audio_path)
		except OSError:
			size = 0
		use_batch = diarization or size > constants.STT_REALTIME_MAX_BYTES or _wav_seconds(audio_path) > 29
		if not use_batch:
			try:
				return self.speech_to_text(
					audio_path, language_code=language_code, model=model, mode=mode,
					keyterms=keyterms, with_timestamps=with_timestamps, cancel=cancel)
			except errors.InvalidRequestError as e:
				low = (e.message or "").lower()
				if not any(w in low for w in ("duration", "30 second", "too long", "length")):
					raise
				logger.info("Real-time STT rejected the clip as too long; using batch.")
		logger.info("Using batch transcription (%d bytes, diarization=%s)." % (size, diarization))
		return self.speech_to_text_batch(
			audio_path, language_code=language_code, model=model, mode=mode,
			keyterms=keyterms, with_timestamps=with_timestamps or diarization,
			diarization=diarization, num_speakers=num_speakers,
			cancel=cancel, progress=progress)

	def speech_to_text_batch(self, audio_path, language_code=None, model=None, mode=None,
			keyterms=None, with_timestamps=False, diarization=False, num_speakers=None,
			cancel=None, progress=None, poll_interval=4.0, max_wait=3 * 3600):
		"""Full batch speech-to-text lifecycle for long audio (up to 2 hours)."""
		filename = os.path.basename(audio_path)

		def step(i, n):
			if progress:
				progress(i, n)

		step(0, 6)
		model = model or models.DEFAULT_STT_MODEL
		params = {"model": model}
		if language_code and language_code not in ("unknown", constants.AUTO_DETECT):
			params["language_code"] = language_code
		else:
			params["language_code"] = "unknown"
		if mode:
			params["mode"] = mode
		if with_timestamps:
			params["with_timestamps"] = True
		if diarization:
			params["with_diarization"] = True
			if num_speakers:
				params["num_speakers"] = int(num_speakers)
		terms = _clean_keyterms(keyterms)
		if terms and models.stt_supports_keyterms(model):
			params["keyterms"] = terms
		created = self._post_json(constants.EP_STT_JOB, {"job_parameters": params}, cancel=cancel)
		job_id = created.get("job_id")
		storage = created.get("storage_container_type")
		if not job_id:
			raise errors.SarvamError(_("Sarvam did not return a transcription job id."))

		step(1, 6)
		up = self._post_json(constants.EP_STT_JOB_UPLOAD,
			{"job_id": job_id, "files": [filename]}, cancel=cancel)
		upload_urls = up.get("upload_urls") or {}
		details = upload_urls.get(filename) or (list(upload_urls.values())[0] if upload_urls else None)
		if not details or not details.get("file_url"):
			raise errors.SarvamError(_("Sarvam did not return an upload URL for the audio."))

		step(2, 6)
		with open(audio_path, "rb") as f:
			self._put_url(details["file_url"], f.read(), storage_type=storage,
				content_type=_guess_audio_ctype(audio_path))

		step(3, 6)
		self._request("POST", constants.EP_STT_JOB_START.format(job_id=job_id), cancel=cancel)

		step(4, 6)
		status = self._poll(
			lambda: self._request("GET", constants.EP_STT_JOB_STATUS.format(job_id=job_id), cancel=cancel),
			lambda s: s.get("job_state"), constants.JOB_TERMINAL_STATES, ("Failed",),
			cancel, poll_interval, max_wait, _("Transcription"))
		state = status.get("job_state")

		step(5, 6)
		body = {"job_id": job_id}
		outputs = _batch_output_files(status)
		if outputs:
			body["files"] = outputs
		dl = self._post_json(constants.EP_STT_JOB_DOWNLOAD, body, cancel=cancel)
		download_urls = dl.get("download_urls") or {}
		texts, segments = [], []
		for name in sorted(download_urls, key=_natural_key):
			det = download_urls[name]
			url = det.get("file_url") if isinstance(det, dict) else None
			if not url:
				continue
			t, segs = _extract_transcript(name, self._get_url(url))
			texts.append(t)
			segments.extend(segs)
		step(6, 6)
		text = "\n".join(t for t in texts if t).strip()
		if not text:
			raise errors.SarvamError(_("No transcript was produced from the audio."))
		return {"transcript": text, "segments": segments, "job_id": job_id,
			"state": state, "language_code": None}

	# -- translation & language --------------------------------------------
	def translate(self, text, source_language_code, target_language_code,
			model=None, mode=None, speaker_gender=None, output_script=None,
			numerals_format=None, enable_preprocessing=False, cancel=None):
		model = model or models.DEFAULT_TRANSLATE_MODEL
		payload = {
			"input": text,
			"source_language_code": source_language_code or constants.AUTO_DETECT,
			"target_language_code": target_language_code,
			"model": model,
		}
		if enable_preprocessing:
			payload["enable_preprocessing"] = True
		# Styles (mode) and speaker gender are Mayura features.
		if mode and model.startswith("mayura"):
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

	def translate_long(self, text, source_language_code, target_language_code,
			model=None, mode=None, cancel=None, progress=None, concurrency=1):
		"""Translate text of any length (split on sentence boundaries, then
		translated - optionally several pieces at once - and re-joined)."""
		from . import tasks as _tasks
		limit = min(constants.TRANSLATE_MAX_CHARS,
			models.translate_info(model or models.DEFAULT_TRANSLATE_MODEL)["max_chars"])
		chunks = _chunk_text(text, limit)
		total = len(chunks)
		if progress:
			progress(0, total)
		done = [0]

		def one(chunk):
			if cancel:
				cancel.check()
			r = self.translate(
				chunk, source_language_code=source_language_code,
				target_language_code=target_language_code,
				model=model, mode=mode, cancel=cancel)
			done[0] += 1
			if progress:
				progress(done[0], total)
			return r.get("translated_text", "")

		if total == 1:
			return one(chunks[0])
		parts = _tasks.parallel_map(one, chunks, concurrency=concurrency, cancel=cancel)
		return "\n\n".join(p for p in parts if p)

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
		res = self._post_json(constants.EP_TEXT_LID, {"input": text[:1000]}, cancel=cancel)
		return {
			"language_code": res.get("language_code"),
			"script_code": res.get("script_code"),
		}

	# -- chat / agents --------------------------------------------------------
	def chat_message(self, messages, model=None, temperature=None, max_tokens=None,
			reasoning_effort=None, tools=None, tool_choice=None, response_format=None,
			cancel=None):
		"""POST /v2/chat/completions and return the assistant message dict
		(``content``, ``tool_calls``, ``reasoning_content``) plus
		``finish_reason``.

		* ``messages`` - OpenAI-style messages; content may be a string or a
		  list of ``text`` / ``image_url`` parts (images must be inline base64).
		* ``reasoning_effort`` - normalised to what the model accepts; if the
		  API still rejects it, the request is retried without it.
		* Sarvam 105B falls back to the legacy V1 endpoint if V2 is refused.
		"""
		model = model or models.DEFAULT_CHAT_MODEL
		payload = {"model": model, "messages": messages}
		if temperature is not None:
			payload["temperature"] = float(temperature)
		if max_tokens:
			payload["max_tokens"] = int(max_tokens)
		effort = models.normalise_effort(model, reasoning_effort) if reasoning_effort else None
		if effort and not (effort == "none" and model == "gemma4"):
			# Gemma 4 thinks only when asked; "off" is expressed by omission.
			payload["reasoning_effort"] = effort
		if tools:
			payload["tools"] = tools
			payload["tool_choice"] = tool_choice or "auto"
		if response_format:
			payload["response_format"] = response_format
		try:
			res = self._post_json(constants.EP_CHAT_COMPLETIONS, payload, cancel=cancel)
		except errors.InvalidRequestError as e:
			low = (e.message or "").lower()
			if "reasoning" in low and "reasoning_effort" in payload:
				logger.info("Model rejected reasoning_effort=%s; retrying without it." % effort)
				payload.pop("reasoning_effort", None)
				res = self._post_json(constants.EP_CHAT_COMPLETIONS, payload, cancel=cancel)
			elif e.status == 404 and model == "sarvam-105b":
				logger.info("Chat V2 not available; retrying Sarvam 105B on V1.")
				res = self._post_json(constants.EP_CHAT_COMPLETIONS_V1, payload, cancel=cancel)
			elif e.status == 404:
				raise errors.InvalidRequestError(
					_("The model {model} is not available to your Sarvam key. "
						"Choose another model in Model switching.").format(model=model),
					code=e.code, request_id=e.request_id, status=e.status)
			else:
				raise
		try:
			choice = res["choices"][0]
			msg = dict(choice.get("message") or {})
			msg["finish_reason"] = choice.get("finish_reason")
			msg["usage"] = res.get("usage")
			return msg
		except (KeyError, IndexError, TypeError):
			raise errors.SarvamError(_("Sarvam returned an empty chat response."))

	def chat(self, messages, model=None, temperature=None, max_tokens=None,
			reasoning_effort=None, wiki_grounding=None, response_format=None, cancel=None):
		"""Return just the assistant's text. (``wiki_grounding`` is accepted for
		backward compatibility but no longer sent - it is not part of the
		current API.)"""
		msg = self.chat_message(
			messages, model=model, temperature=temperature, max_tokens=max_tokens,
			reasoning_effort=reasoning_effort, response_format=response_format, cancel=cancel)
		content = msg.get("content")
		if isinstance(content, list):
			content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
		if not content:
			if msg.get("finish_reason") == "length":
				raise errors.SarvamError(_(
					"The model ran out of output space before answering. Lower the "
					"reasoning effort or raise the maximum response length in Advanced settings."))
			raise errors.SarvamError(_("Sarvam returned an empty chat response."))
		return content

	def summarize(self, text, instruction=None, model=None, cancel=None):
		instruction = instruction or _("Summarise the following text clearly and concisely.")
		messages = [
			{"role": "system", "content": instruction},
			{"role": "user", "content": text},
		]
		return self.chat(messages, model=model, cancel=cancel)

	def describe_image(self, image_bytes, mime="image/jpeg", prompt=None, model=None,
			cancel=None):
		"""Describe an image with a vision model (Gemma 4 by default)."""
		model = model or models.DEFAULT_VISION_MODEL
		if not models.supports_vision(model):
			model = models.DEFAULT_VISION_MODEL
		system = next(r[2] for r in constants.WORKFORCE_ROLES if r[0] == constants.VISION_ROLE)
		messages = [
			{"role": "system", "content": system},
			{"role": "user", "content": [
				{"type": "text", "text": prompt or _("Describe this image in detail.")},
				image_part(image_bytes, mime),
			]},
		]
		return self.chat(messages, model=model,
			reasoning_effort=models.default_effort(model), cancel=cancel)

	# -- presigned URLs -------------------------------------------------------
	def _put_url(self, url, data, storage_type=None, content_type=None, extra_headers=None):
		"""Upload ``data`` to a presigned URL with a raw PUT."""
		headers = {"User-Agent": _USER_AGENT,
			"Content-Type": content_type or "application/octet-stream"}
		if (storage_type and str(storage_type).lower().startswith("azure")) or "blob.core" in url:
			headers["x-ms-blob-type"] = "BlockBlob"
		if extra_headers:
			headers.update(extra_headers)
		req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
		try:
			with self._opener().open(req, timeout=max(self._timeout(), 300)) as resp:
				resp.read()
		except urllib.error.HTTPError as e:
			body = b""
			try:
				body = e.read()
			except Exception:
				pass
			raise errors.SarvamError(
				_("Uploading the file failed (HTTP {code}). {body}").format(
					code=e.code, body=body.decode("utf-8", "replace")[:200]))
		except (urllib.error.URLError, OSError) as e:
			raise errors.NetworkError(
				_("Could not upload the file: {err}").format(err=getattr(e, "reason", e)))

	def _get_url(self, url, headers=None):
		"""Download bytes from a presigned URL with a raw GET (no auth header)."""
		hdrs = {"User-Agent": _USER_AGENT}
		if headers:
			hdrs.update(headers)
		req = urllib.request.Request(url, headers=hdrs, method="GET")
		try:
			with self._opener().open(req, timeout=max(self._timeout(), 300)) as resp:
				return resp.read()
		except urllib.error.HTTPError as e:
			raise errors.SarvamError(
				_("Downloading the result failed (HTTP {code}).").format(code=e.code))
		except (urllib.error.URLError, OSError) as e:
			raise errors.NetworkError(
				_("Could not download the result: {err}").format(err=getattr(e, "reason", e)))

	def _poll(self, fetch, state_of, terminal, failed, cancel, interval, max_wait, what):
		waited = 0.0
		while waited < max_wait:
			if cancel:
				cancel.check()
			status = fetch() or {}
			state = state_of(status)
			logger.debug("%s state=%s" % (what, state))
			if state in failed:
				msg = (status.get("error_message") or status.get("error")
					or status.get("detail") or state)
				if isinstance(msg, dict):
					msg = msg.get("message") or json.dumps(msg)
				raise errors.SarvamError(_("{what} failed: {msg}").format(what=what, msg=msg))
			if state in terminal:
				return status
			_sleep(interval, cancel)
			waited += interval
		raise errors.SarvamError(_("{what} timed out. Please try again.").format(what=what))

	# -- documents: Document AI (current) with legacy fallback ---------------
	def document_ocr(self, path, language=None, output_format=None,
			cancel=None, progress=None):
		"""Read a document (PDF, PNG, JPEG, ZIP of page images) and return its
		text with structure preserved.

		Uses Sarvam Document AI (``/doc-ai/v1``) unless the configured engine is
		"legacy", and falls back to the legacy digitization API automatically
		if Document AI is not available to the key. Other image types (BMP,
		TIFF, GIF, WebP) are converted to a one-page PDF first.
		"""
		from . import imaging
		ext = os.path.splitext(path)[1].lower()
		temp = None
		if ext not in constants.DOCAI_DIRECT_EXTENSIONS:
			path, is_temp = imaging.ensure_pdf(path)
			temp = path if is_temp else None
		try:
			engine = self._cfg.conf().get("docEngine") or models.DEFAULT_DOC_ENGINE
			if engine != "legacy":
				try:
					return self.docai_parse(path, language=language,
						output_format=output_format, cancel=cancel, progress=progress)
				except errors.InvalidRequestError as e:
					if e.status not in (404, 405):
						raise
					logger.info("Document AI unavailable (HTTP %s); using legacy OCR." % e.status)
			# The legacy API takes only PDF or ZIP.
			pdf, is_temp = ((path, False) if path.lower().endswith((".pdf", ".zip"))
				else imaging.ensure_pdf(path))
			try:
				return self.legacy_document_ocr(pdf, language=language,
					output_format=output_format, cancel=cancel, progress=progress)
			finally:
				if is_temp:
					_remove(pdf)
		finally:
			if temp:
				_remove(temp)

	def docai_parse(self, path, language=None, output_format=None, cancel=None,
			progress=None, poll_interval=3.0, max_wait=1800):
		"""Document AI parse: upload -> poll -> download ZIP -> text."""
		output_format = output_format or constants.DEFAULT_OCR_OUTPUT_FORMAT
		if progress:
			progress(0, 4)
		with open(path, "rb") as f:
			data = f.read()
		fields = {"output_format": output_format}
		if language and language not in (constants.OCR_AUTO_LANGUAGE, "unknown"):
			fields["language"] = language
		files = [("file", os.path.basename(path), data, mime_type(path))]
		created = self._post_multipart(constants.EP_DOCAI_PARSE, fields, files, cancel=cancel)
		job_id = created.get("job_id")
		if not job_id:
			raise errors.SarvamError(_("Sarvam did not return a document job id."))
		if progress:
			progress(1, 4)
		status = self._docai_wait(job_id, cancel, poll_interval, max_wait)
		if progress:
			progress(2, 4)
		text = ""
		try:
			dl = self._request("GET", constants.EP_DOCAI_DOWNLOAD_URL.format(job_id=job_id), cancel=cancel)
			url = dl.get("url") or dl.get("download_url")
			if url:
				blob = self._get_url(url, headers=dl.get("headers") or None)
				text = _extract_ocr_text(os.path.basename(path), blob, output_format)
		except errors.InvalidRequestError:
			text = ""
		if not text.strip():
			# Results endpoint returns page contents directly.
			res = self._request("GET", constants.EP_DOCAI_RESULTS.format(job_id=job_id)
				+ "?format=" + urllib.parse.quote(output_format), cancel=cancel)
			pages = []
			for doc in res.get("documents") or []:
				for page in sorted(doc.get("pages") or [], key=lambda p: p.get("page_number") or 0):
					if page.get("content"):
						pages.append(page["content"])
			text = "\n\n".join(pages)
		if progress:
			progress(4, 4)
		text = (text or "").strip()
		if not text:
			raise errors.SarvamError(_("No text could be extracted from the document."))
		usage = status.get("usage") or {}
		return {"text": text, "job_id": job_id, "state": status.get("status"),
			"format": output_format, "pages": usage.get("pages_total")}

	def docai_extract(self, path, schema, output_format="csv", mode="basic",
			language=None, cancel=None, progress=None, poll_interval=3.0, max_wait=1800):
		"""Document AI extract: pull named fields/tables out of a document.

		``schema`` is a JSON-schema dict (root type object). Returns
		``{"data": dict-or-None, "file_bytes": bytes-or-None, "format": ...}``:
		JSON results are returned as data; CSV/XLSX as the downloaded file.
		"""
		from . import imaging
		ext = os.path.splitext(path)[1].lower()
		temp = None
		if ext not in constants.DOCAI_DIRECT_EXTENSIONS:
			path, is_temp = imaging.ensure_pdf(path)
			temp = path if is_temp else None
		try:
			if progress:
				progress(0, 3)
			with open(path, "rb") as f:
				data = f.read()
			fields = {
				"schema": json.dumps(schema, ensure_ascii=False),
				"output_format": output_format,
				"mode": mode or "basic",
			}
			if language and language not in (constants.OCR_AUTO_LANGUAGE, "unknown"):
				fields["language"] = language
			files = [("file", os.path.basename(path), data, mime_type(path))]
			created = self._post_multipart(constants.EP_DOCAI_EXTRACT, fields, files, cancel=cancel)
			job_id = created.get("job_id")
			if not job_id:
				raise errors.SarvamError(_("Sarvam did not return an extraction job id."))
			if progress:
				progress(1, 3)
			self._docai_wait(job_id, cancel, poll_interval, max_wait)
			if progress:
				progress(2, 3)
			result = {"data": None, "file_bytes": None, "format": output_format, "job_id": job_id}
			res = self._request("GET", constants.EP_DOCAI_RESULTS.format(job_id=job_id), cancel=cancel)
			result["data"] = res.get("result") if isinstance(res, dict) else None
			if output_format in ("csv", "xlsx"):
				dl = self._request("GET", constants.EP_DOCAI_DOWNLOAD_URL.format(job_id=job_id), cancel=cancel)
				url = dl.get("url") or dl.get("download_url")
				if url:
					result["file_bytes"] = self._get_url(url, headers=dl.get("headers") or None)
			if progress:
				progress(3, 3)
			return result
		finally:
			if temp:
				_remove(temp)

	def _docai_wait(self, job_id, cancel, interval, max_wait):
		return self._poll(
			lambda: self._request("GET", constants.EP_DOCAI_STATUS.format(job_id=job_id), cancel=cancel),
			lambda s: (s.get("status") or "").lower(),
			constants.DOCAI_DONE_STATES, constants.DOCAI_FAILED_STATES,
			cancel, interval, max_wait, _("Document processing"))

	def legacy_document_ocr(self, pdf_path, language=None, output_format=None,
			cancel=None, progress=None, poll_interval=3.0, max_wait=600):
		"""The pre-2.0 document digitization flow (fallback only)."""
		output_format = output_format or constants.DEFAULT_OCR_OUTPUT_FORMAT
		filename = os.path.basename(pdf_path)

		def step(i, n):
			if progress:
				progress(i, n)

		step(0, 6)
		job_params = {"output_format": output_format}
		if language and language != constants.OCR_AUTO_LANGUAGE:
			job_params["language"] = constants.LEGACY_OCR_LANGUAGE_MAP.get(language, language)
		created = self._post_json(constants.EP_OCR_CREATE, {"job_parameters": job_params}, cancel=cancel)
		job_id = created.get("job_id")
		storage = created.get("storage_container_type")
		if not job_id:
			raise errors.SarvamError(_("Sarvam did not return an OCR job id."))
		step(1, 6)
		up = self._post_json(constants.EP_OCR_UPLOAD, {"job_id": job_id, "files": [filename]}, cancel=cancel)
		upload_urls = up.get("upload_urls") or {}
		details = upload_urls.get(filename) or (list(upload_urls.values())[0] if upload_urls else None)
		if not details or not details.get("file_url"):
			raise errors.SarvamError(_("Sarvam did not return an upload URL."))
		step(2, 6)
		with open(pdf_path, "rb") as f:
			self._put_url(details["file_url"], f.read(), storage_type=storage)
		step(3, 6)
		self._request("POST", constants.EP_OCR_START.format(job_id=job_id), cancel=cancel)
		step(4, 6)
		status = self._poll(
			lambda: self._request("GET", constants.EP_OCR_STATUS.format(job_id=job_id), cancel=cancel),
			lambda s: s.get("job_state"), constants.OCR_TERMINAL_STATES, ("Failed",),
			cancel, poll_interval, max_wait, _("OCR"))
		step(5, 6)
		dl = self._request("POST", constants.EP_OCR_DOWNLOAD.format(job_id=job_id), cancel=cancel)
		download_urls = dl.get("download_urls") or {}
		if not download_urls:
			raise errors.SarvamError(_("Sarvam returned no OCR output. The document may be empty."))
		texts = []
		for name, det in download_urls.items():
			url = det.get("file_url") if isinstance(det, dict) else None
			if url:
				texts.append(_extract_ocr_text(name, self._get_url(url), output_format))
		step(6, 6)
		text = "\n\n".join(t for t in texts if t).strip()
		if not text:
			raise errors.SarvamError(_("No text could be extracted from the document."))
		return {"text": text, "job_id": job_id, "state": status.get("job_state"), "format": output_format}

	# -- document translation (keeps the file format) -----------------------
	def translate_document(self, path, source_language_code, target_language_codes,
			out_dir, genre=None, cancel=None, progress=None, poll_interval=10.0,
			max_wait=3 * 3600):
		"""Translate a whole file (PDF, Word, Excel, PowerPoint, HTML, Markdown
		or text) and save one translated copy per target language, in the
		same format as the original, into ``out_dir``. Returns the saved paths.
		"""
		filename = os.path.basename(path)
		targets = [t for t in target_language_codes if t]
		if not targets:
			raise errors.InvalidRequestError(_("Choose at least one target language."))
		src = source_language_code
		if not src or src in (constants.AUTO_DETECT, "unknown"):
			src = "en-IN"
		body = {
			"source_language_code": src,
			"target_language_codes": targets[:12],
			"original_filename": filename,
			"job_name": os.path.splitext(filename)[0][:255] or "document",
		}
		if genre:
			body["genre"] = genre
		if progress:
			progress(0, 100)
		created = self._post_json(constants.EP_DOCTR_CREATE, body, cancel=cancel)
		job_id = created.get("job_id")
		upload_url = created.get("upload_url")
		if not job_id or not upload_url:
			raise errors.SarvamError(_("Sarvam did not return a document translation job."))
		with open(path, "rb") as f:
			data = f.read()
		extra = {constants.AUTH_HEADER: self._key()} if upload_url.startswith(self._base()) else None
		self._put_url(upload_url, data, storage_type="azure", content_type=mime_type(path),
			extra_headers=extra)
		self._request("POST", constants.EP_DOCTR_START.format(job_id=job_id), cancel=cancel)

		def fetch():
			s = self._request("GET", constants.EP_DOCTR_STATUS.format(job_id=job_id), cancel=cancel)
			if progress and isinstance(s.get("progress"), (int, float)):
				progress(int(s["progress"]), 100)
			return s

		status = self._poll(fetch, lambda s: s.get("job_state"),
			("Completed", "PartiallyCompleted"), ("Failed",),
			cancel, poll_interval, max_wait, _("Document translation"))
		done_langs = [t.get("target_language_code") for t in status.get("translations") or []
			if t.get("state") == "Completed"] or targets
		saved = []
		base, ext = os.path.splitext(filename)
		for lang in done_langs:
			self._request("POST", constants.EP_DOCTR_EXPORT.format(job_id=job_id)
				+ "?lang=" + urllib.parse.quote(lang), cancel=cancel)
			exp = self._poll(
				lambda: self._request("GET", constants.EP_DOCTR_EXPORT_STATUS.format(job_id=job_id), cancel=cancel),
				lambda s: s.get("export_state") if s.get("target_language_code") in (None, lang) else "Pending",
				("Completed",), ("Failed",), cancel, 3.0, 1800, _("Export"))
			url = exp.get("download_url")
			if not url:
				raise errors.SarvamError(_("Sarvam did not return a download link for {lang}.").format(lang=lang))
			blob = self._get_url(url)
			name = exp.get("filename") or "%s_%s%s" % (base, lang, ext)
			out = unique_path(os.path.join(out_dir, os.path.basename(name)))
			with open(out, "wb") as f:
				f.write(blob)
			saved.append(out)
		if progress:
			progress(100, 100)
		return saved


	# -- dubbing --------------------------------------------------------------
	def dub(self, path, source_language, target_languages, out_dir,
			export_options=("video",), voice_cloning=True, num_speakers=1,
			register=None, voice_id=None, pace_preset=None,
			disable_watermark=False, cancel=None, progress=None,
			poll_interval=10.0, max_wait=6 * 3600):
		"""Dub a video or audio file into one or more Indian languages.

		Flow (Sarvam Dubbing API): POST /dubbing/jobs -> PUT the media to the
		signed upload_url -> POST start -> poll live-status until the job
		finishes -> poll export-status (the source of truth for downloads)
		until every requested (language, format) export is done -> download
		each one. Files are saved into ``out_dir`` as
		``<name>_<language>.<ext>``; the saved paths are returned.
		"""
		targets = [constants.to_dub_language(t) for t in target_languages if t]
		src = constants.to_dub_language(source_language or "auto")
		targets = [t for t in targets if t != src]
		if not targets:
			raise errors.InvalidRequestError(
				_("Choose at least one target language different from the source language."))
		exports = [e for e in (export_options or ("video",))]
		name = os.path.basename(path)
		body = {
			"src_lang": src,
			"target_langs": targets,
			"export_options": exports,
			"voice_cloning": bool(voice_cloning),
			"job_name": os.path.splitext(name)[0][:200] or "dub",
		}
		if num_speakers:
			body["num_speakers"] = int(num_speakers)
		if register and register != "auto":
			body["register"] = register
		if not voice_cloning:
			if voice_id:
				body["voice_id"] = voice_id.strip().lower()
			if pace_preset:
				body["pace_preset"] = pace_preset
		if disable_watermark:
			body["disable_watermark"] = True
		if progress:
			progress(0, 100)
		created = self._post_json(constants.EP_DUB_CREATE, body, cancel=cancel)
		data = created.get("data") if isinstance(created.get("data"), dict) else created
		job_id = data.get("job_id")
		upload_url = data.get("upload_url")
		if not job_id or not upload_url:
			raise errors.SarvamError(_("Sarvam did not return a dubbing job."))
		with open(path, "rb") as f:
			self._put_url(upload_url, f.read(), storage_type="azure", content_type=mime_type(path))
		if cancel:
			cancel.check()
		self._request("POST", constants.EP_DUB_START.format(job_id=job_id), cancel=cancel)

		def unwrap(res):
			return res.get("data") if isinstance(res, dict) and isinstance(res.get("data"), dict) else (res or {})

		def fetch():
			s = unwrap(self._request("GET", constants.EP_DUB_STATUS.format(job_id=job_id), cancel=cancel))
			if progress and isinstance(s.get("progress"), (int, float)):
				progress(min(95, int(s["progress"])), 100)
			return s

		self._poll(fetch, lambda s: (s.get("status") or "").lower(),
			constants.DUB_DONE_STATES, constants.DUB_FAILED_STATES,
			cancel, poll_interval, max_wait, _("Dubbing"))

		# Wait for every requested export; the list can be empty for a short
		# while right after the job completes.
		wanted = len(targets) * len(exports)
		waited = 0.0
		items = []
		while True:
			res = unwrap(self._request("GET", constants.EP_DUB_EXPORTS.format(job_id=job_id), cancel=cancel))
			items = [e for e in (res.get("exports") or []) if isinstance(e, dict)]
			settled = [e for e in items if e.get("status") in ("completed", "failed")]
			if items and len(items) >= wanted and len(settled) == len(items):
				break
			if waited >= 1800:
				break
			_sleep(5.0, cancel)
			waited += 5.0
		saved = []
		base = os.path.splitext(name)[0]
		for e in items:
			if e.get("status") != "completed" or e.get("is_stale") or not e.get("download_url"):
				continue
			ext = constants.DUB_EXPORT_EXTENSIONS.get(e.get("export_type"), ".bin")
			out = unique_path(os.path.join(out_dir, "%s_%s%s" % (base, e.get("target_language", ""), ext)))
			with open(out, "wb") as f:
				f.write(self._get_url(e["download_url"]))
			saved.append(out)
		if progress:
			progress(100, 100)
		if not saved:
			failed = [e for e in items if e.get("status") == "failed"]
			raise errors.SarvamError(
				_("Dubbing finished but no file could be downloaded ({n} exports failed).").format(n=len(failed)))
		return saved


# --- module-level helpers ---------------------------------------------------
def image_part(image_bytes, mime="image/jpeg", detail="auto"):
	"""A chat content part carrying an inline base64 image."""
	return {"type": "image_url", "image_url": {
		"url": "data:%s;base64,%s" % (mime, base64.b64encode(image_bytes).decode("ascii")),
		"detail": detail}}


def unique_path(path):
	"""``path`` or, if it exists, ``name (2).ext``, ``name (3).ext`` ..."""
	if not os.path.exists(path):
		return path
	base, ext = os.path.splitext(path)
	n = 2
	while os.path.exists("%s (%d)%s" % (base, n, ext)):
		n += 1
	return "%s (%d)%s" % (base, n, ext)


def _remove(path):
	try:
		os.remove(path)
	except OSError:
		pass


def _clean_keyterms(keyterms):
	if not keyterms:
		return []
	if isinstance(keyterms, str):
		import re
		keyterms = re.split(r"[,\n;]+", keyterms)
	out = []
	for t in keyterms:
		t = (t or "").strip()[:constants.STT_MAX_KEYTERM_CHARS]
		if t and t not in out:
			out.append(t)
	return out[:constants.STT_MAX_KEYTERMS]


def _wav_seconds(path):
	"""Duration of a WAV file in seconds (0 for other formats or errors)."""
	if not path.lower().endswith(".wav"):
		return 0
	try:
		import wave
		with wave.open(path, "rb") as wf:
			return wf.getnframes() / float(wf.getframerate() or 1)
	except Exception:
		return 0


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
		raise errors.InvalidRequestError(_("There is no text to process."))
	if len(text) <= limit:
		return [text]
	chunks = []
	current = ""
	import re
	parts = re.split(r"(?<=[.!?।॥\n])\s+", text)
	for part in parts:
		while len(part) > limit:
			cut = part.rfind(" ", 0, limit)
			cut = cut if cut > limit // 2 else limit
			chunks.append(part[:cut])
			part = part[cut:].lstrip()
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
		return {"transcript": str(res), "language_code": None, "segments": []}
	segments = []
	ts = res.get("timestamps")
	if isinstance(ts, dict):
		words = ts.get("words") or []
		starts = ts.get("start_time_seconds") or []
		ends = ts.get("end_time_seconds") or []
		for i, w in enumerate(words):
			segments.append({
				"text": w,
				"start": starts[i] if i < len(starts) else None,
				"end": ends[i] if i < len(ends) else None,
				"speaker": None})
	return {
		"transcript": res.get("transcript", res.get("text", "")),
		"language_code": res.get("language_code") or res.get("detected_language_code"),
		"request_id": res.get("request_id"),
		"segments": segments,
	}


def _batch_output_files(status):
	"""Output file names listed in a batch job status (if any)."""
	names = []
	for det in status.get("job_details") or []:
		if not isinstance(det, dict):
			continue
		for out in det.get("outputs") or []:
			if isinstance(out, dict) and out.get("file_name"):
				names.append(out["file_name"])
	return names


def _extract_ocr_text(name, blob, output_format):
	"""Turn a document result payload (a ZIP of md/html/json, or a single
	file) into readable text."""
	import io
	import zipfile

	def to_text(fname, data):
		try:
			raw = data.decode("utf-8", "replace")
		except Exception:
			return ""
		low = fname.lower()
		if low.endswith(".json") or (output_format == "json" and not low.endswith((".md", ".html", ".htm"))):
			return _json_to_text(raw)
		if low.endswith((".html", ".htm")):
			return raw if output_format == "html" else _strip_html(raw)
		return raw

	if blob[:2] == b"PK":
		parts = []
		try:
			with zipfile.ZipFile(io.BytesIO(blob)) as zf:
				names = [n for n in zf.namelist() if not n.endswith("/")]
				# Document AI ZIPs hold the primary file plus metadata/*.json and
				# manifest.json; read the primary output only when present.
				wanted = {"md": (".md",), "html": (".html", ".htm"), "json": (".json",)}.get(
					output_format, (".md",))
				primary = [n for n in names if n.lower().endswith(wanted)
					and not n.lower().startswith("metadata/") and os.path.basename(n).lower() != "manifest.json"]
				for info in sorted(primary or names, key=_natural_key):
					parts.append(to_text(info, zf.read(info)))
		except zipfile.BadZipFile:
			return blob.decode("utf-8", "replace")
		return "\n\n".join(p for p in parts if p and p.strip())
	return to_text(name, blob)


def _natural_key(name):
	"""Sort key that orders embedded numbers numerically (page2 < page10)."""
	import re
	return [int(p) if p.isdigit() else p.lower()
		for p in re.split(r"(\d+)", name)]


def _extract_transcript(name, blob):
	"""Return ``(text, segments)`` from a batch STT result (JSON or a ZIP of
	JSON). Diarized output is rendered as "Speaker 1: ..." lines."""
	import io
	import zipfile

	def one(data):
		try:
			obj = json.loads(data.decode("utf-8", "replace"))
		except Exception:
			return data.decode("utf-8", "replace"), []
		if not isinstance(obj, dict):
			return str(obj), []
		segs = []
		dia = obj.get("diarized_transcript")
		entries = dia.get("entries") if isinstance(dia, dict) else (dia if isinstance(dia, list) else None)
		if entries:
			lines = []
			speakers = {}
			for e in entries:
				if not isinstance(e, dict):
					continue
				spk = str(e.get("speaker_id", ""))
				label = speakers.setdefault(spk, _("Speaker {n}").format(n=len(speakers) + 1))
				txt = (e.get("transcript") or "").strip()
				segs.append({"text": txt, "start": e.get("start_time_seconds"),
					"end": e.get("end_time_seconds"), "speaker": label})
				lines.append("%s: %s" % (label, txt))
			return "\n".join(lines), segs
		norm = _normalise_transcript(obj)
		return norm["transcript"], norm["segments"]

	if blob[:2] == b"PK":
		texts, segs = [], []
		try:
			with zipfile.ZipFile(io.BytesIO(blob)) as zf:
				for info in sorted(zf.namelist(), key=_natural_key):
					if not info.endswith("/"):
						t, s = one(zf.read(info))
						texts.append(t)
						segs.extend(s)
		except zipfile.BadZipFile:
			return blob.decode("utf-8", "replace"), []
		return "\n".join(t for t in texts if t), segs
	return one(blob)


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
	text = re.sub(r"(?i)<br\s*/?>|</p>|</h[1-6]>|</li>|</tr>|</div>", "\n", text)
	text = re.sub(r"(?s)<[^>]+>", " ", text)
	text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
		.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
	text = re.sub(r"[ \t]+", " ", text)
	text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
	return text.strip()


def _concat_wav(wavs):
	"""Concatenate a list of WAV byte strings into a single WAV."""
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
