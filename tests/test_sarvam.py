# -*- coding: UTF-8 -*-
"""Tests for the Sarvam AI assistant add-on, runnable outside NVDA:

    python -m unittest discover -s tests -v

NVDA and wx are replaced by stubs (tests/nvda_stubs.py). The Sarvam API is
replaced by a fake transport that records each request and returns canned
responses shaped like Sarvam's documented responses.
"""

import base64
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import warnings
import wave
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nvda_stubs  # noqa: E402

warnings.simplefilter("ignore", ResourceWarning)
nvda_stubs.install()
CFG = nvda_stubs.fresh_config()

from sarvamAI import agent, client, constants, errors, exporter, models, textextract, ttsstyles  # noqa: E402


def _wav(seconds=0.1, rate=8000):
	buf = io.BytesIO()
	with wave.open(buf, "wb") as w:
		w.setnchannels(1)
		w.setsampwidth(2)
		w.setframerate(rate)
		w.writeframes(b"\x00\x00" * int(rate * seconds))
	return buf.getvalue()


class FakeTransport:
	"""Replaces SarvamClient._request / _get_url / _put_url."""

	def __init__(self, cli, handler):
		self.calls = []
		self.handler = handler
		cli._request = self._request
		cli._get_url = lambda url, headers=None: self.handler("GETURL", url, None)
		cli._put_url = lambda url, data, **k: self.calls.append(("PUT", url, len(data)))

	def _request(self, method, path, headers=None, data=None, cancel=None, expect_json=True):
		body = None
		if data is not None:
			ctype = (headers or {}).get("Content-Type", "")
			body = json.loads(data.decode("utf-8")) if ctype.startswith("application/json") else data
		self.calls.append((method, path, body))
		return self.handler(method, path, body)


def make_client():
	CFG.setApiKey("sk_test_key")
	cli = client.SarvamClient(CFG)
	client._sleep = lambda s, c=None: None  # no waiting in tests
	return cli


class VoiceCatalogueTests(unittest.TestCase):

	def test_v4_catalogue_size_and_shape(self):
		self.assertEqual(len(ttsstyles.V4_VOICE_IDS), 222)
		self.assertEqual(len(set(ttsstyles.V4_VOICE_IDS)), 222)
		self.assertEqual(len(ttsstyles.V3_SPEAKERS), 37)

	def test_every_voice_has_gender_language_and_known_purpose(self):
		for v in ttsstyles.ALL_SPEAKERS:
			self.assertIn(ttsstyles.gender_of(v), ttsstyles.GENDERS, v)
			for p in ttsstyles.purposes_of(v):
				self.assertIn(p, ttsstyles.PURPOSE_KEYS, v)
		for v in ttsstyles.V4_VOICE_IDS:
			_n, lang, tag = ttsstyles.parse_v4(v)
			self.assertIn(lang, ttsstyles.V4_LANGUAGE_TAGS, v)
			self.assertIn(tag, ttsstyles.PURPOSE_TAGS, v)

	def test_documented_genders(self):
		# Sarvam's own "recommended male / female" tables.
		for v in ("simran_en_sales", "zarina_en_conversation", "aparna_hi_kyc", "aarti_hi_customer"):
			self.assertEqual(ttsstyles.gender_of(v), "Female")
		for v in ("sunny_en_social", "rohan_en_recovery", "shubh_hi_ecomm", "ratan_hi_customer_expressive"):
			self.assertEqual(ttsstyles.gender_of(v), "Male")

	def test_classification_never_empty(self):
		langs = [None, "auto"] + list(constants.LANGUAGES)
		for model in ttsstyles.MODELS:
			for g in ttsstyles.GENDERS:
				for p in ttsstyles.PURPOSE_KEYS:
					for lang in langs:
						vs = ttsstyles.voices_for(g, p, model=model, language=lang)
						self.assertTrue(vs)
						for v in vs:
							self.assertEqual(ttsstyles.model_of(v), model)

	def test_language_filter_v4(self):
		kn = ttsstyles.voices_for("Female", None, model=ttsstyles.MODEL_V4, language="kn-IN")
		self.assertTrue(all("_kn_" in v for v in kn))
		hi = ttsstyles.voices_for(None, None, model=ttsstyles.MODEL_V4, language="hi-IN")
		self.assertTrue(any("_enhi_" in v for v in hi))

	def test_purpose_mapping(self):
		self.assertIn("customer", ttsstyles.purposes_of("ritu_hi_banking"))
		self.assertIn("formal", ttsstyles.purposes_of("ritu_hi_banking"))
		self.assertIn("narration", ttsstyles.purposes_of("shubh_en_audiobook"))
		self.assertIn("devotional", ttsstyles.purposes_of("girish_hi_devotional"))
		self.assertIn("expressive", ttsstyles.purposes_of("simran_hi_social_excited"))
		avail = ttsstyles.purposes_available(ttsstyles.MODEL_V4, "Female", "hi-IN")
		self.assertTrue(all(n > 0 for _k, _l, n in avail))

	def test_labels(self):
		self.assertEqual(ttsstyles.voice_label("ritu_hi_customer_warm"),
			"Ritu - Hindi - Customer warm (female)")
		self.assertEqual(ttsstyles.voice_label("shubh"), "Shubh (male)")

	def test_defaults_valid(self):
		for model in ttsstyles.MODELS:
			v = ttsstyles.default_voice("Male", "news", model=model)
			self.assertTrue(ttsstyles.is_valid_speaker(v, model))
		self.assertTrue(ttsstyles.is_valid_speaker(ttsstyles.V4_DEFAULT_SPEAKER, ttsstyles.MODEL_V4))


class ModelCatalogueTests(unittest.TestCase):

	def test_chat_models(self):
		ids = models.chat_ids()
		for m in ("sarvam-105b", "glm5.3", "glm5.3-flash", "gemma4", "deepseekv4.1-flash-1017"):
			self.assertIn(m, ids)
		for retired in models.RETIRED_CHAT_MODELS:
			self.assertNotIn(retired, ids)
		self.assertIn("gemma4", models.vision_ids())
		self.assertNotIn("sarvam-105b", models.vision_ids())

	def test_effort_normalisation(self):
		self.assertEqual(models.normalise_effort("glm5.3-flash", "medium"), "high")
		self.assertEqual(models.normalise_effort("glm5.3-flash", "low"), "low")
		self.assertEqual(models.normalise_effort("sarvam-105b", "max"), "medium")
		self.assertEqual(models.normalise_effort("kimi-k3.1-pro", "none"), "high")

	def test_descriptions(self):
		for key, _label, catalogue, default, _cfg in models.SERVICES:
			self.assertIn(default, [m["id"] for m in catalogue])
			for m in catalogue:
				self.assertIn(m["id"], models.describe(key, m["id"]))

	def test_migration_from_1x(self):
		import config as nvda_config
		sec = nvda_config.conf[CFG.SECTION]
		sec.update({"chatModel": "sarvam-30b", "ttsModel": "bulbul:v2", "sttModel": "saarika:v2.5",
			"migratedTo2": False, "ttsStyle": "storytelling", "ocrLanguage": "or-IN"})
		CFG._migrateStaleValues()
		self.assertEqual(sec["chatModel"], "sarvam-105b")
		self.assertEqual(sec["ttsModel"], "bulbul:v4-flash")
		self.assertEqual(sec["sttModel"], "saaras:v4")
		self.assertEqual(sec["ttsStyle"], "conversational")
		self.assertEqual(sec["ocrLanguage"], "od-IN")
		self.assertTrue(sec["migratedTo2"])


SAMPLE_MD = """# Report

Intro paragraph with **bold**.

- first
- second

## Prices

| Item | Qty | Price |
|---|---|---|
| ಅಕ್ಕಿ rice | 2 | 120 |
| Dal | 1 | 95.5 |
"""


class ExporterTests(unittest.TestCase):

	def setUp(self):
		self.dir = tempfile.mkdtemp()

	def tearDown(self):
		shutil.rmtree(self.dir, ignore_errors=True)

	def test_all_formats(self):
		segs = [{"text": "hello", "start": 0.0, "end": 1.25, "speaker": "Speaker 1"},
			{"text": "world", "start": 61.5, "end": 63.0, "speaker": None}]
		for fmt in exporter.format_keys(include_tables=True, include_srt=True):
			path = os.path.join(self.dir, "out" + exporter.extension(fmt))
			exporter.export(SAMPLE_MD, path, fmt, title="T", segments=segs)
			self.assertTrue(os.path.getsize(path) > 0, fmt)
		# Office files must be valid zips with well-formed XML.
		for name in ("out.docx", "out.xlsx"):
			with zipfile.ZipFile(os.path.join(self.dir, name)) as z:
				for part in z.namelist():
					if part.endswith(".xml") or part.endswith(".rels"):
						ET.fromstring(z.read(part))
		html = open(os.path.join(self.dir, "out.html"), encoding="utf-8").read()
		self.assertIn("<table>", html)
		self.assertIn("<h2>Prices</h2>", html)
		self.assertIn("<li>first</li>", html)
		srt = open(os.path.join(self.dir, "out.srt"), encoding="utf-8").read()
		self.assertIn("00:01:01,500 --> 00:01:03,000", srt)
		self.assertIn("Speaker 1: hello", srt)
		csv_text = open(os.path.join(self.dir, "out.csv"), encoding="utf-8-sig").read()
		self.assertIn("ಅಕ್ಕಿ rice,2,120", csv_text)
		data = json.load(open(os.path.join(self.dir, "out.json"), encoding="utf-8"))
		self.assertEqual(data["tables"][0]["rows"][1][0], "ಅಕ್ಕಿ rice")

	def test_round_trips_through_reader(self):
		x = os.path.join(self.dir, "t.xlsx")
		exporter.export(SAMPLE_MD, x, "xlsx")
		text = textextract.extract_text(x)
		self.assertIn("ಅಕ್ಕಿ rice", text)
		self.assertIn("95.5", text)
		d = os.path.join(self.dir, "t.docx")
		exporter.export(SAMPLE_MD, d, "docx")
		self.assertIn("ಅಕ್ಕಿ rice", textextract.extract_text(d))
		r = os.path.join(self.dir, "t.rtf")
		exporter.export("ನಮಸ್ಕಾರ world 😀\nline two", r, "rtf")
		rt = textextract.extract_text(r)
		self.assertIn("ನಮಸ್ಕಾರ world", rt)
		self.assertIn("line two", rt)
		h = os.path.join(self.dir, "t.html")
		exporter.export(SAMPLE_MD, h, "html")
		self.assertIn("Dal", textextract.extract_text(h))

	def test_srt_needs_timings(self):
		with self.assertRaises(errors.SarvamError):
			exporter.export("x", os.path.join(self.dir, "a.srt"), "srt", segments=[])


class TextExtractTests(unittest.TestCase):

	def setUp(self):
		self.dir = tempfile.mkdtemp()

	def tearDown(self):
		shutil.rmtree(self.dir, ignore_errors=True)

	def test_pptx(self):
		p = os.path.join(self.dir, "s.pptx")
		slide = ('<p:sld xmlns:p="p" xmlns:a="a"><a:p><a:r><a:t>Title &amp; one</a:t></a:r></a:p>'
			'<a:p><a:r><a:t>Point</a:t></a:r></a:p></p:sld>')
		with zipfile.ZipFile(p, "w") as z:
			z.writestr("ppt/slides/slide2.xml", slide.replace("one", "two"))
			z.writestr("ppt/slides/slide1.xml", slide)
		text = textextract.extract_text(p)
		self.assertLess(text.index("Title & one"), text.index("Title & two"))

	def test_subtitles_and_odt(self):
		s = os.path.join(self.dir, "a.srt")
		with open(s, "w", encoding="utf-8") as f:
			f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\n<i>There</i>\n")
		self.assertEqual(textextract.extract_text(s), "Hello\nThere")
		o = os.path.join(self.dir, "a.odt")
		with zipfile.ZipFile(o, "w") as z:
			z.writestr("content.xml", '<x><text:p>One<text:s text:c="2"/>two</text:p><text:h>Head</text:h></x>')
		self.assertEqual(textextract.extract_text(o), "One  two\nHead")


class ClientTests(unittest.TestCase):

	def test_chat_v2_with_tools_and_effort_fallback(self):
		cli = make_client()
		state = {"n": 0}

		def handler(method, path, body):
			state["n"] += 1
			if state["n"] == 1:
				raise errors.InvalidRequestError("reasoning_effort not supported", status=400)
			return {"choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}]}

		t = FakeTransport(cli, handler)
		msg = cli.chat_message([{"role": "user", "content": "x"}], model="glm5.3-flash",
			reasoning_effort="medium", tools=list(agent.TOOLS))
		self.assertEqual(msg["content"], "hi")
		first, second = t.calls[0][2], t.calls[1][2]
		self.assertEqual(t.calls[0][1], "/v2/chat/completions")
		self.assertEqual(first["reasoning_effort"], "high")  # normalised for GLM flash
		self.assertNotIn("reasoning_effort", second)
		self.assertEqual(first["tool_choice"], "auto")
		self.assertNotIn("wiki_grounding", first)

	def test_gemma_effort_off_is_omitted(self):
		cli = make_client()
		t = FakeTransport(cli, lambda m, p, b: {"choices": [{"message": {"content": "ok"}}]})
		cli.chat([{"role": "user", "content": "x"}], model="gemma4", reasoning_effort="none")
		self.assertNotIn("reasoning_effort", t.calls[0][2])

	def test_tts_v4_falls_back_to_v3_for_malayalam(self):
		cli = make_client()
		audio = base64.b64encode(_wav()).decode()
		t = FakeTransport(cli, lambda m, p, b: {"audios": [audio]})
		out = cli.text_to_speech("നമസ്കാരം", "ml-IN", speaker="ritu_hi_banking",
			model="bulbul:v4-flash", pace=1.0, temperature=0.6, output_audio_codec="wav")
		body = t.calls[0][2]
		self.assertEqual(body["model"], "bulbul:v3")
		self.assertEqual(ttsstyles.gender_of(body["speaker"]), "Female")
		self.assertIn(body["speaker"], ttsstyles.V3_SPEAKERS)
		for banned in ("pitch", "loudness", "enable_preprocessing"):
			self.assertNotIn(banned, body)
		self.assertTrue(cli.last_tts_note)
		self.assertEqual(out[:4], b"RIFF")

	def test_tts_long_text_chunks_and_joins(self):
		cli = make_client()
		audio = base64.b64encode(_wav()).decode()
		t = FakeTransport(cli, lambda m, p, b: {"audios": [audio]})
		text = ("ಇದು ಒಂದು ವಾಕ್ಯ. " * 400).strip()
		out = cli.text_to_speech(text, "kn-IN", speaker="chaitra_kn_narration",
			model="bulbul:v4-flash", output_audio_codec="wav", concurrency=3)
		self.assertGreater(len(t.calls), 1)
		self.assertTrue(all(len(c[2]["text"]) <= 2500 for c in t.calls))
		with wave.open(io.BytesIO(out)) as w:
			self.assertEqual(w.getnframes(), 800 * len(t.calls))

	def test_docai_parse_flow(self):
		cli = make_client()
		zbuf = io.BytesIO()
		with zipfile.ZipFile(zbuf, "w") as z:
			z.writestr("doc.md", "# Heading\n\nBody")
			z.writestr("metadata/page_001.json", '{"x": 1}')
			z.writestr("manifest.json", "{}")
		states = iter(["pending", "running", "completed"])

		def handler(method, path, body):
			if path == "/doc-ai/v1/job/parse":
				return {"job_id": "J1", "status": "pending"}
			if path.endswith("/status"):
				return {"job_id": "J1", "status": next(states), "usage": {"pages_total": 3}}
			if path.endswith("/download-url"):
				return {"url": "https://blob/x", "method": "GET"}
			if method == "GETURL":
				return zbuf.getvalue()
			raise AssertionError(path)

		FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			pdf = os.path.join(d, "a.pdf")
			open(pdf, "wb").write(b"%PDF-1.4")
			res = cli.document_ocr(pdf, language="kn-IN", output_format="md")
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertEqual(res["text"], "# Heading\n\nBody")
		self.assertEqual(res["pages"], 3)

	def test_docai_404_falls_back_to_legacy(self):
		cli = make_client()

		def handler(method, path, body):
			if path.startswith("/doc-ai"):
				raise errors.InvalidRequestError("not found", status=404)
			if path == constants.EP_OCR_CREATE:
				self.assertEqual(body["job_parameters"]["language"], "or-IN")
				return {"job_id": "L1"}
			if path == constants.EP_OCR_UPLOAD:
				return {"upload_urls": {"a.pdf": {"file_url": "https://up"}}}
			if path.endswith("/start"):
				return {}
			if path.endswith("/status"):
				return {"job_state": "Completed"}
			if path.endswith("/download-files"):
				return {"download_urls": {"r.md": {"file_url": "https://dl"}}}
			if method == "GETURL":
				return "legacy text".encode()
			raise AssertionError(path)

		FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			pdf = os.path.join(d, "a.pdf")
			open(pdf, "wb").write(b"%PDF-1.4")
			res = cli.document_ocr(pdf, language="od-IN")
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertEqual(res["text"], "legacy text")

	def test_batch_stt_with_diarization(self):
		cli = make_client()
		result = {"transcript": "a b", "diarized_transcript": {"entries": [
			{"transcript": "Namaskara", "start_time_seconds": 0.0, "end_time_seconds": 1.0, "speaker_id": "S0"},
			{"transcript": "Hello", "start_time_seconds": 1.0, "end_time_seconds": 2.0, "speaker_id": "S1"}]}}

		def handler(method, path, body):
			if path == constants.EP_STT_JOB:
				self.assertTrue(body["job_parameters"]["with_diarization"])
				self.assertEqual(body["job_parameters"]["keyterms"], ["Sarvam", "Bengaluru"])
				self.assertEqual(body["job_parameters"]["mode"], "codemix")
				return {"job_id": "S1"}
			if path == constants.EP_STT_JOB_UPLOAD:
				return {"upload_urls": {"a.wav": {"file_url": "https://up"}}}
			if path.endswith("/start"):
				return {}
			if path.endswith("/status"):
				return {"job_state": "Completed", "job_details": [{"outputs": [{"file_name": "0.json"}]}]}
			if path == constants.EP_STT_JOB_DOWNLOAD:
				self.assertEqual(body["files"], ["0.json"])
				return {"download_urls": {"0.json": {"file_url": "https://dl"}}}
			if method == "GETURL":
				return json.dumps(result).encode()
			raise AssertionError(path)

		FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			wav = os.path.join(d, "a.wav")
			open(wav, "wb").write(_wav(1.0))
			res = cli.transcribe(wav, language_code="unknown", mode="codemix",
				keyterms="Sarvam, Bengaluru", diarization=True)
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertEqual(res["transcript"], "Speaker 1: Namaskara\nSpeaker 2: Hello")
		self.assertEqual(res["segments"][1]["speaker"], "Speaker 2")

	def test_short_clip_too_long_retries_batch(self):
		cli = make_client()
		calls = []

		def handler(method, path, body):
			calls.append(path)
			if path == constants.EP_SPEECH_TO_TEXT:
				raise errors.InvalidRequestError("Audio duration exceeds 30 seconds", status=400)
			if path == constants.EP_STT_JOB:
				return {"job_id": "S2"}
			if path == constants.EP_STT_JOB_UPLOAD:
				return {"upload_urls": {"a.mp3": {"file_url": "https://up"}}}
			if path.endswith("/start"):
				return {}
			if path.endswith("/status"):
				return {"job_state": "Completed"}
			if path == constants.EP_STT_JOB_DOWNLOAD:
				return {"download_urls": {"0.json": {"file_url": "https://dl"}}}
			if method == "GETURL":
				return b'{"transcript": "long audio"}'
			raise AssertionError(path)

		FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			mp3 = os.path.join(d, "a.mp3")
			open(mp3, "wb").write(b"ID3" + b"\x00" * 1000)
			res = cli.transcribe(mp3)
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertEqual(res["transcript"], "long audio")
		self.assertIn(constants.EP_STT_JOB, calls)

	def test_translate_document(self):
		cli = make_client()
		exported = {"n": 0}

		def handler(method, path, body):
			if path == constants.EP_DOCTR_CREATE:
				self.assertEqual(body["target_language_codes"], ["kn-IN"])
				self.assertEqual(body["original_filename"], "letter.docx")
				return {"job_id": "D1", "upload_url": "https://api.sarvam.ai/translate/document/uploads/D1?sig=x"}
			if path.endswith("/start"):
				return {"job_state": "Accepted"}
			if path.endswith("/live-status"):
				return {"job_state": "Completed", "progress": 100,
					"translations": [{"target_language_code": "kn-IN", "state": "Completed"}]}
			if "/export?lang=kn-IN" in path:
				exported["n"] += 1
				return {}
			if path.endswith("/export/status"):
				return {"export_state": "Completed", "target_language_code": "kn-IN",
					"download_url": "https://dl", "filename": "letter_kn-IN.docx"}
			if method == "GETURL":
				return b"PK translated"
			raise AssertionError(path)

		t = FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			src = os.path.join(d, "letter.docx")
			open(src, "wb").write(b"PK original")
			out = cli.translate_document(src, "en-IN", ["kn-IN"], d)
			self.assertEqual(os.path.basename(out[0]), "letter_kn-IN.docx")
			self.assertEqual(open(out[0], "rb").read(), b"PK translated")
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertEqual(exported["n"], 1)
		self.assertTrue(any(c[0] == "PUT" for c in t.calls))


class DubbingTests(unittest.TestCase):

	def test_dub_flow(self):
		cli = make_client()
		states = iter(["queued", "in_progress", "completed"])
		export_polls = {"n": 0}

		def handler(method, path, body):
			if path == constants.EP_DUB_CREATE:
				self.assertEqual(body["src_lang"], "en-IN")
				self.assertEqual(body["target_langs"], ["kn-IN", "or-IN"])  # od-IN mapped
				self.assertEqual(body["export_options"], ["video", "srt"])
				self.assertTrue(body["voice_cloning"])
				self.assertNotIn("voice_id", body)
				return {"status": "success", "data": {"job_id": "dub_1",
					"upload_url": "https://api.sarvam.ai/dubbing/uploads/dub_1?sig=x"}}
			if path.endswith("/start"):
				return {"status": "success"}
			if path.endswith("/live-status"):
				return {"data": {"job_id": "dub_1", "status": next(states), "progress": 50}}
			if "/export-status" in path:
				export_polls["n"] += 1
				if export_polls["n"] == 1:
					return {"data": {"exports": []}}  # empty right after completion
				return {"data": {"exports": [
					{"id": "e1", "export_type": "video", "target_language": "kn-IN", "status": "completed",
						"is_stale": False, "download_url": "https://dl/1"},
					{"id": "e2", "export_type": "srt", "target_language": "kn-IN", "status": "completed",
						"is_stale": False, "download_url": "https://dl/2"},
					{"id": "e3", "export_type": "video", "target_language": "or-IN", "status": "completed",
						"is_stale": False, "download_url": "https://dl/3"},
					{"id": "e4", "export_type": "srt", "target_language": "or-IN", "status": "failed",
						"is_stale": False}]}}
			if method == "GETURL":
				return b"media:" + path.encode()
			raise AssertionError(path)

		t = FakeTransport(cli, handler)
		d = tempfile.mkdtemp()
		try:
			src = os.path.join(d, "talk.mp4")
			with open(src, "wb") as f:
				f.write(b"\x00" * 64)
			saved = cli.dub(src, "en-IN", ["kn-IN", "od-IN"], d, export_options=["video", "srt"])
			names = sorted(os.path.basename(p) for p in saved)
			self.assertEqual(names, ["talk_kn-IN.mp4", "talk_kn-IN.srt", "talk_or-IN.mp4"])
		finally:
			shutil.rmtree(d, ignore_errors=True)
		self.assertTrue(any(c[0] == "PUT" for c in t.calls))
		self.assertEqual(export_polls["n"], 2)

	def test_dub_rejects_same_source_and_target(self):
		cli = make_client()
		FakeTransport(cli, lambda m, p, b: {})
		with self.assertRaises(errors.InvalidRequestError):
			cli.dub("x.mp4", "hi-IN", ["hi-IN"], tempfile.gettempdir())

	def test_preset_voice_sent_only_without_cloning(self):
		cli = make_client()
		seen = {}

		def handler(method, path, body):
			if path == constants.EP_DUB_CREATE:
				seen.update(body)
				raise errors.InvalidRequestError("stop here", status=400)
			raise AssertionError(path)

		FakeTransport(cli, handler)
		with self.assertRaises(errors.InvalidRequestError):
			cli.dub("x.wav", "auto", ["ta-IN"], tempfile.gettempdir(), export_options=["audio"],
				voice_cloning=False, voice_id=" Ishita ", pace_preset="slow", num_speakers=-1)
		self.assertEqual(seen["voice_id"], "ishita")
		self.assertEqual(seen["pace_preset"], "slow")
		self.assertEqual(seen["num_speakers"], -1)


class AgentTests(unittest.TestCase):

	def test_safe_file_name(self):
		self.assertEqual(agent.safe_file_name("..\\..\\evil/../x.docx", ".docx"), "x.docx")
		self.assertEqual(agent.safe_file_name("report", ".mp3"), "report.mp3")
		self.assertEqual(agent.safe_file_name("con", ".txt"), "_con.txt")
		self.assertEqual(agent.safe_file_name('a<b>:c', ".md"), "a_b__c.md")

	def test_agent_loop_runs_tools_and_saves_inside_output_folder(self):
		out_dir = tempfile.mkdtemp()
		try:
			cli = make_client()
			audio = base64.b64encode(_wav()).decode()
			turns = iter([
				{"choices": [{"message": {"content": "", "tool_calls": [
					{"id": "c1", "type": "function", "function": {"name": "read_attached_file",
						"arguments": json.dumps({"index": 1})}}]}, "finish_reason": "tool_calls"}]},
				{"choices": [{"message": {"content": "", "tool_calls": [
					{"id": "c2", "type": "function", "function": {"name": "translate_text",
						"arguments": json.dumps({"text": "Hello", "target_language": "kn-IN"})}},
					{"id": "c3", "type": "function", "function": {"name": "save_document",
						"arguments": json.dumps({"content": "# T\n\nನಮಸ್ಕಾರ", "file_name": "../../x",
							"format": "docx"})}},
					{"id": "c4", "type": "function", "function": {"name": "create_speech_file",
						"arguments": json.dumps({"text": "ನಮಸ್ಕಾರ", "language": "kn-IN",
							"gender": "Female", "purpose": "narration", "file_name": "speech"})}},
				]}, "finish_reason": "tool_calls"}]},
				{"choices": [{"message": {"content": "Done: saved x.docx and speech.mp3"}, "finish_reason": "stop"}]},
			])

			def handler(method, path, body):
				if path == constants.EP_CHAT_COMPLETIONS:
					return next(turns)
				if path == constants.EP_TRANSLATE:
					return {"translated_text": "ನಮಸ್ಕಾರ"}
				if path == constants.EP_TEXT_TO_SPEECH:
					self.assertTrue(body["speaker"].endswith("_kn_narration") or "_kn_" in body["speaker"])
					self.assertEqual(ttsstyles.gender_of(body["speaker"]), "Female")
					return {"audios": [audio]}
				raise AssertionError(path)

			t = FakeTransport(cli, handler)
			tools = agent.AgentTools(cli, CFG.conf(), [("letter.txt", "Hello")], out_dir)
			steps = []
			messages = [{"role": "user", "content": "do it"}]
			reply = agent.run_agent(cli, messages, "sarvam-105b", tools, effort="medium",
				on_step=steps.append)
			self.assertEqual(reply, "Done: saved x.docx and speech.mp3")
			self.assertEqual(sorted(os.listdir(out_dir)), ["speech.mp3", "x.docx"])
			for p in tools.saved_files:
				self.assertEqual(os.path.dirname(p), out_dir)
			tool_msgs = [m for m in messages if m["role"] == "tool"]
			self.assertEqual([m["tool_call_id"] for m in tool_msgs], ["c1", "c2", "c3", "c4"])
			self.assertIn("Hello", tool_msgs[0]["content"])
			self.assertTrue(any("Translating" in s for s in steps))
			self.assertEqual(t.calls[0][2]["tools"][0]["type"], "function")
		finally:
			shutil.rmtree(out_dir, ignore_errors=True)

	def test_schema_parsing_and_rendering(self):
		s = agent.parse_schema('Here: {"invoice_number": {"type": "string", "description": "n"}}')
		self.assertEqual(s["type"], "object")
		self.assertIn("invoice_number", s["properties"])
		md = agent.extract_result_to_markdown({"invoice_number": "A1", "items": [
			{"name": "Rice", "qty": 2}, {"name": "Dal", "qty": 1, "price": 95}]})
		self.assertIn("| invoice number | A1 |", md)
		self.assertIn("| name | qty | price |", md)
		tables = exporter.tables_from_markdown(md)
		self.assertEqual(len(tables), 2)


class DialogSmokeTests(unittest.TestCase):
	"""Construct every dialog against the wx stub to catch name/attribute
	errors in constructors and handlers."""

	def test_construct_dialogs(self):
		from sarvamAI.ui import tts, stt, translate, ocr_dialog, workforce, models as models_ui, setup, dubbing
		import sarvamAI
		for factory in (
				lambda: dubbing.DubbingDialog(None),
				lambda: tts.TextToSpeechDialog(None, initial_text="hello"),
				lambda: stt.SpeechToTextDialog(None),
				lambda: translate.TranslateDialog(None, initial_text="x"),
				lambda: ocr_dialog.OcrDialog(None),
				lambda: workforce.WorkforceDialog(None, mode="agent"),
				lambda: workforce.WorkforceDialog(None, initial_image=(b"x", "image/png", "shot")),
				lambda: models_ui.ModelCenterDialog(None),
				lambda: setup.SetupDialog(None)):
			dlg = factory()
			self.assertIsNotNone(dlg)
		plugin = sarvamAI.GlobalPlugin()
		self.assertTrue(hasattr(plugin, "onModels"))
		self.assertIn("Chat model", models_ui.cycle_chat_model(1))

	def test_default_gestures(self):
		import sarvamAI
		bound = {}
		for name in dir(sarvamAI.GlobalPlugin):
			if name.startswith("script_"):
				info = getattr(getattr(sarvamAI.GlobalPlugin, name), "_scriptInfo", {})
				if info.get("gesture"):
					bound[info["gesture"]] = name
		# Exactly one default key: NVDA+Alt+A describes the screen.
		self.assertEqual(bound, {"kb:NVDA+alt+a": "script_describeScreen"})

	def test_tts_dialog_classification_flow(self):
		from sarvamAI.ui import tts
		d = tts.TextToSpeechDialog(None, initial_text="hello")
		d.modelCtrl.SetSelection(d._modelIds.index("bulbul:v4-flash"))
		d.langCtrl.SetSelection(d._langCodes.index("kn-IN"))
		d._onLanguage(None)
		self.assertTrue(all("_kn_" in v for v in d._voiceIds))
		d.genderCtrl.SetSelection(d._genders.index("Male"))
		d._onGender(None)
		self.assertTrue(all(ttsstyles.gender_of(v) == "Male" for v in d._voiceIds))
		d.modelCtrl.SetSelection(d._modelIds.index("bulbul:v3"))
		d._onModel(None)
		self.assertTrue(all(v in ttsstyles.V3_SPEAKERS for v in d._voiceIds))
		d._onPurpose(None)
		p = d._params()
		self.assertEqual(p["model"], "bulbul:v3")


if __name__ == "__main__":
	unittest.main()
