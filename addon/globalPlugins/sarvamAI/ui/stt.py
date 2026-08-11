# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Speech to text dialog.

Choose an audio file (or record the microphone), then press Transcribe. Large
audio is handled automatically: files beyond the real-time limit are sent
through Sarvam's batch transcription job API and merged into one complete
transcript, with no manual intervention. Save as TXT / DOCX appears only after
the transcription finishes.
"""

import os

import wx
import gui
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import recorder
from . import common


class SpeechToTextDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the speech to text dialog.
		super().__init__(parent, title=_("Sarvam AI - Speech to Text"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._rec = recorder.MicRecorder()
		self._audioPath = None
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
		labels, self._langCodes = common.language_choices(include_unknown=True)
		# "Auto" is the recommended choice: it also allows a single utterance to
		# mix languages (see onTranscribe).
		self.langCtrl = row.addLabeledControl(
			_("Audio la&nguage (Auto also handles mixed-language speech):"),
			wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("sttLanguage"))
		# Translators: checkbox to translate transcription to English.
		self.translateCtrl = row.addItem(wx.CheckBox(self, label=_("Translate to &English")))
		helper.addItem(row.sizer)

		# Transcribe.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.transcribeBtn = go.addButton(self, label=_("&Transcribe"))
		self.transcribeBtn.Bind(wx.EVT_BUTTON, self.onTranscribe)
		helper.addItem(go)

		# Transcript. TE_RICH2 handles very large documents efficiently.
		self.transcriptCtrl = helper.addLabeledControl(
			_("&Transcript:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 260))

		# Save bar (hidden until transcription succeeds).
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.transcriptCtrl.GetValue(), "transcript")

		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

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
		translate = self.translateCtrl.GetValue()
		conf = config.conf()
		self.transcribeBtn.Enable(False)
		self.saveBar.show(False)

		def work(cancel, progress):
			model = conf.get("sttTranslateModel") if translate else conf.get("sttModel")
			# Auto: let Sarvam work the language out itself ("unknown") and ask
			# for code-mixed output, so a sentence that naturally mixes, say,
			# Kannada and English is transcribed as spoken instead of being
			# forced into a single language. An explicit language keeps the
			# normal single-language transcription behaviour.
			isAuto = lang in ("unknown", constants.AUTO_DETECT)
			if isAuto:
				language = constants.STT_AUTO_LANGUAGE
				mode = (constants.STT_CODEMIX_MODE
					if conf.get("sttCodeSwitching") else constants.DEFAULT_STT_MODE)
			else:
				language = lang
				mode = constants.DEFAULT_STT_MODE
			return self._cli.transcribe(
				path, language_code=language, model=model, translate=translate,
				mode=mode, cancel=cancel, progress=progress)

		def ok(result):
			self.transcribeBtn.Enable(True)
			text = result.get("transcript", "")
			# ChangeValue avoids firing text events for very large transcripts.
			self.transcriptCtrl.ChangeValue(text)
			self.saveBar.show(True)
			# Deliberately not announcing a detected language: for mixed-language
			# speech a single language name is misleading, and repeating it adds
			# noise. The user just gets the transcript.
			common.report(_("Transcribed, {n} characters. Save options are now available.").format(n=len(text)))
			self.transcriptCtrl.SetFocus()

		def bad(exc):
			self.transcribeBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Speech to Text"),
			message=_("Transcribing audio (large files are processed in batches)..."),
			parent=self)

	def _cleanup(self):
		if self._rec.recording:
			self._rec.cancel()
