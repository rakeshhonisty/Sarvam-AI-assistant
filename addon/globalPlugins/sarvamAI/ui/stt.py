# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Speech to text dialog.

Choose an audio file (WAV, MP3, M4A/MP4, AAC, AIFF, FLAC, OGG, Opus, WebM,
AMR, WMA) or record the microphone, pick the output (transcript in the spoken
language, English translation, verbatim, romanised or code-mixed), optionally
add key terms (names and jargon Saaras v4 should spell correctly), ask for
speaker separation or timings, and press Transcribe.

Long audio (up to two hours) and speaker separation automatically use
Sarvam's batch API. The result downloads as text, Word, Markdown, HTML, JSON
or - with timings - as SRT subtitles.
"""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import models
from .. import tasks
from .. import recorder
from . import common

_MODE_AUTO = "auto"


class SpeechToTextDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the speech to text dialog.
		super().__init__(parent, title=_("Sarvam AI - Speech to Text"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._rec = recorder.MicRecorder()
		self._audioPath = None
		self._segments = []
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Source.
		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = srcBtns.addButton(self, label=_("Choose audio &file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		self.recordBtn = srcBtns.addButton(self, label=_("Start &recording"))
		self.recordBtn.Bind(wx.EVT_BUTTON, self.onRecordToggle)
		helper.addItem(srcBtns)
		# Translators: shows the currently selected audio source.
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Source: none selected")))

		# Options.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		labels, self._langCodes = common.language_choices(include_unknown=True, extended=True)
		self.langCtrl = row.addLabeledControl(_("Audio la&nguage:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("sttLanguage"))
		self._modes = [_MODE_AUTO] + list(constants.STT_MODES)
		self.modeCtrl = row.addLabeledControl(
			_("&Output:"), wx.Choice,
			choices=[_("Automatic (code-mixed when the language is Auto)")]
				+ [_(constants.STT_MODE_LABELS[m]) for m in constants.STT_MODES])
		common.select_in_combo(self.modeCtrl, self._modes, conf.get("sttMode") or _MODE_AUTO)
		helper.addItem(row.sizer)

		# Translators: names or jargon the recogniser should spell correctly.
		self.keytermsCtrl = helper.addLabeledControl(
			_("&Key terms to spell correctly, separated by commas (Saaras v4, optional):"),
			wx.TextCtrl)
		self.keytermsCtrl.SetValue(conf.get("sttKeyterms") or "")

		opts = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.diarizeCtrl = opts.addItem(wx.CheckBox(self, label=_("Separate &speakers (who said what)")))
		self.diarizeCtrl.SetValue(bool(conf.get("sttDiarization")))
		self.speakersCtrl = opts.addLabeledControl(
			_("Number of spea&kers (0 = detect):"), wx.SpinCtrl, min=0, max=20)
		self.speakersCtrl.SetValue(0)
		self.timestampsCtrl = opts.addItem(wx.CheckBox(self, label=_("Include t&imings (for subtitles)")))
		self.timestampsCtrl.SetValue(bool(conf.get("sttTimestamps")))
		helper.addItem(opts.sizer)

		# Transcribe.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.transcribeBtn = go.addButton(self, label=_("&Transcribe"))
		self.transcribeBtn.Bind(wx.EVT_BUTTON, self.onTranscribe)
		helper.addItem(go)

		self.transcriptCtrl = helper.addLabeledControl(
			_("Transcrip&t:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 260))

		# Download bar (hidden until transcription succeeds); SRT when timed.
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.transcriptCtrl.GetValue(), "transcript",
			get_segments=lambda: self._segments, title=_("Transcript"))

		more = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.aiBtn = more.addButton(self, label=_("Send to AI &Workforce"))
		self.aiBtn.Bind(wx.EVT_BUTTON, self.onSendToAI)
		closeBtn = more.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(more)
		self.aiBtn.Show(False)

		self._updateTranscribe()
		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self, cleanup=self._cleanup)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	# -- source -------------------------------------------------------------
	def onChooseFile(self, evt):
		exts = ";".join("*" + e for e in constants.AUDIO_EXTENSIONS)
		with wx.FileDialog(self, _("Open audio file"),
				wildcard=_("Audio files (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			self._audioPath = fd.GetPath()
		name = os.path.basename(self._audioPath)
		try:
			mb = os.path.getsize(self._audioPath) / (1024.0 * 1024.0)
			self.sourceLabel.SetLabel(_("Source: {name} ({size:.1f} MB)").format(name=name, size=mb))
		except OSError:
			self.sourceLabel.SetLabel(_("Source: {name}").format(name=name))
		common.report(_("Audio file selected. Press Transcribe."))
		self._updateTranscribe()

	def onRecordToggle(self, evt):
		if self._rec.recording:
			try:
				path = self._rec.stop()
			except recorder.RecorderError as e:
				common.error_dialog(self, e)
				self.recordBtn.SetLabel(_("Start &recording"))
				return
			self.recordBtn.SetLabel(_("Start &recording"))
			self._audioPath = path
			self.sourceLabel.SetLabel(_("Source: microphone recording"))
			common.report(_("Recording stopped. Press Transcribe."))
			self._updateTranscribe()
		else:
			try:
				self._rec.start()
			except recorder.RecorderError as e:
				common.error_dialog(self, e)
				return
			self.recordBtn.SetLabel(_("&Stop recording"))
			common.report(_("Recording. Press the button again to stop."))

	def _updateTranscribe(self):
		self.transcribeBtn.Enable(bool(self._audioPath))

	# -- transcription ------------------------------------------------------
	def onTranscribe(self, evt):
		if not self._audioPath or not os.path.isfile(self._audioPath):
			common.report(_("Choose an audio file or record first"))
			return
		path = self._audioPath
		lang = self._langCodes[self.langCtrl.GetSelection()]
		mode = self._modes[self.modeCtrl.GetSelection()]
		keyterms = self.keytermsCtrl.GetValue().strip()
		diarize = self.diarizeCtrl.GetValue()
		speakers = int(self.speakersCtrl.GetValue()) or None
		timings = self.timestampsCtrl.GetValue()
		conf = config.conf()
		conf["sttLanguage"] = lang
		conf["sttMode"] = mode
		conf["sttKeyterms"] = keyterms
		conf["sttDiarization"] = diarize
		conf["sttTimestamps"] = timings
		model = conf.get("sttModel") or models.DEFAULT_STT_MODEL
		self.transcribeBtn.Enable(False)
		self.saveBar.show(False)

		def work(cancel, progress):
			isAuto = lang in ("unknown", constants.AUTO_DETECT)
			language = constants.STT_AUTO_LANGUAGE if isAuto else lang
			if mode == _MODE_AUTO:
				# Auto language + code switching keeps naturally mixed speech
				# (e.g. Kannada with English words) as it was spoken.
				real_mode = (constants.STT_CODEMIX_MODE if isAuto and conf.get("sttCodeSwitching")
					else constants.DEFAULT_STT_MODE)
			else:
				real_mode = mode
			return self._cli.transcribe(
				path, language_code=language, model=model, mode=real_mode,
				keyterms=keyterms, with_timestamps=timings, diarization=diarize,
				num_speakers=speakers, cancel=cancel, progress=progress)

		def ok(result):
			self.transcribeBtn.Enable(True)
			text = result.get("transcript", "")
			self._segments = result.get("segments") or []
			self.transcriptCtrl.ChangeValue(text)
			self.saveBar.show(True)
			self.aiBtn.Show(True)
			self.Layout()
			msg = _("Transcribed, {n} characters. Download options are now available.").format(n=len(text))
			if keyterms and not models.stt_supports_keyterms(model):
				msg += " " + _("Key terms need Saaras v4; switch models in Model switching.")
			common.report(msg)
			self.transcriptCtrl.SetFocus()

		def bad(exc):
			self.transcribeBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Speech to Text"),
			message=_("Transcribing audio (long files are processed as a batch job)..."),
			parent=self)

	def onSendToAI(self, evt):
		text = self.transcriptCtrl.GetValue().strip()
		if text:
			from .workforce import WorkforceDialog
			WorkforceDialog(self, initial_context=text, context_name=_("transcript")).Show()

	def _cleanup(self):
		if self._rec.recording:
			self._rec.cancel()
