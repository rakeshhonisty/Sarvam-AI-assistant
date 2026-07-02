# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Speech to text dialog: pick an audio file or record the microphone, then
press Transcribe to send it to Sarvam. Optionally translate to English. Save
the transcript as plain text or a Word document."""

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
from .. import docwriter
from .. import logger
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

		labels, self._langCodes = common.language_choices(include_unknown=True)
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.langCtrl = row.addLabeledControl(_("Audio la&nguage:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("sttLanguage"))
		# Translators: checkbox to translate transcription to English.
		self.translateCtrl = row.addItem(wx.CheckBox(self, label=_("Translate to &English")))
		helper.addItem(row.sizer)

		# Source selection.
		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = srcBtns.addButton(self, label=_("Choose audio &file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		self.recordBtn = srcBtns.addButton(self, label=_("Start &recording"))
		self.recordBtn.Bind(wx.EVT_BUTTON, self.onRecordToggle)
		helper.addItem(srcBtns)

		# Translators: shows the currently selected audio source.
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Source: none selected")))

		# The Transcribe trigger.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.transcribeBtn = go.addButton(self, label=_("&Transcribe"))
		self.transcribeBtn.Bind(wx.EVT_BUTTON, self.onTranscribe)
		helper.addItem(go)

		self.transcriptCtrl = helper.addLabeledControl(
			_("&Transcript:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(560, 220))

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.copyBtn = btns.addButton(self, label=_("&Copy"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.saveTxtBtn = btns.addButton(self, label=_("Save as &text (.txt)"))
		self.saveTxtBtn.Bind(wx.EVT_BUTTON, self.onSaveTxt)
		self.saveDocBtn = btns.addButton(self, label=_("Save as &Word (.docx)"))
		self.saveDocBtn.Bind(wx.EVT_BUTTON, self.onSaveDocx)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self._updateTranscribe()
		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	# -- source selection ---------------------------------------------------
	def onChooseFile(self, evt):
		exts = ";".join("*" + e for e in constants.AUDIO_EXTENSIONS)
		with wx.FileDialog(
				self, _("Open audio file"),
				wildcard=_("Audio files (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			self._audioPath = fd.GetPath()
		self.sourceLabel.SetLabel(_("Source: {name}").format(name=os.path.basename(self._audioPath)))
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

		def work(cancel, progress):
			if translate:
				return self._cli.speech_to_text_translate(
					path, model=conf.get("sttTranslateModel"), cancel=cancel)
			language = None if lang in ("unknown", constants.AUTO_DETECT) else lang
			return self._cli.speech_to_text(
				path, language_code=language, model=conf.get("sttModel"), cancel=cancel)

		def ok(result):
			self.transcribeBtn.Enable(True)
			self.transcriptCtrl.SetValue(result.get("transcript", ""))
			detected = result.get("language_code")
			if detected:
				common.report(_("Transcribed. Detected language {lang}").format(lang=detected))
			else:
				common.report(_("Transcribed"))
			self.transcriptCtrl.SetFocus()

		def bad(exc):
			self.transcribeBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Speech to Text"),
			message=_("Transcribing audio..."), parent=self)

	def _updateTranscribe(self):
		self.transcribeBtn.Enable(bool(self._audioPath))

	# -- output -------------------------------------------------------------
	def onCopy(self, evt):
		text = self.transcriptCtrl.GetValue()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			common.report(_("Copied"))
		else:
			common.report(_("Nothing to copy"))

	def onSaveTxt(self, evt):
		self._save("transcript.txt", _("Text files (*.txt)|*.txt"), docwriter.write_txt)

	def onSaveDocx(self, evt):
		self._save("transcript.docx", _("Word documents (*.docx)|*.docx"), docwriter.write_docx)

	def _save(self, default_name, wildcard, writer):
		text = self.transcriptCtrl.GetValue()
		if not text.strip():
			common.report(_("Nothing to save"))
			return
		with wx.FileDialog(
				self, _("Save transcript"), defaultDir=common.default_output_folder(),
				defaultFile=default_name, wildcard=wildcard,
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			writer(text, path)
			common.report(_("Saved"))
		except Exception as e:
			common.error_dialog(self, e)

	def _onClose(self, evt):
		if self._rec.recording:
			self._rec.cancel()
		self.Destroy()
