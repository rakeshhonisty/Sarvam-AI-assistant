# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Speech to text dialog: transcribe an audio file or the microphone, with an
optional translate-to-English mode."""

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
from .. import logger
from . import common


class SpeechToTextDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the speech to text dialog.
		super().__init__(parent, title=_("Sarvam AI - Speech to Text"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._rec = recorder.MicRecorder()
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		labels, self._langCodes = common.language_choices(include_unknown=True)
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.langCtrl = row.addLabeledControl(_("Audio la&nguage:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("sttLanguage"))
		# Translators: checkbox to translate transcription to English.
		self.translateCtrl = row.addItem(wx.CheckBox(self, label=_("Translate to &English")))
		helper.addItem(row.sizer)

		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = srcBtns.addButton(self, label=_("Transcribe audio &file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onFile)
		self.recordBtn = srcBtns.addButton(self, label=_("Start &recording"))
		self.recordBtn.Bind(wx.EVT_BUTTON, self.onRecordToggle)
		helper.addItem(srcBtns)

		# Translators: field showing the transcript.
		self.transcriptCtrl = helper.addLabeledControl(
			_("&Transcript:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(560, 240))

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.copyBtn = btns.addButton(self, label=_("&Copy transcript"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.saveBtn = btns.addButton(self, label=_("&Save transcript..."))
		self.saveBtn.Bind(wx.EVT_BUTTON, self.onSave)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	def onFile(self, evt):
		exts = ";".join("*" + e for e in constants.AUDIO_EXTENSIONS)
		with wx.FileDialog(
				self, _("Open audio file"),
				wildcard=_("Audio files (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		self._transcribe(path)

	def onRecordToggle(self, evt):
		if self._rec.recording:
			try:
				path = self._rec.stop()
			except recorder.RecorderError as e:
				common.error_dialog(self, e)
				self.recordBtn.SetLabel(_("Start &recording"))
				return
			self.recordBtn.SetLabel(_("Start &recording"))
			common.report(_("Recording stopped, transcribing"))
			if path:
				self._transcribe(path)
		else:
			try:
				self._rec.start()
			except recorder.RecorderError as e:
				common.error_dialog(self, e)
				return
			self.recordBtn.SetLabel(_("&Stop recording and transcribe"))
			common.report(_("Recording. Press the button again to stop."))

	def _transcribe(self, path):
		lang = self._langCodes[self.langCtrl.GetSelection()]
		translate = self.translateCtrl.GetValue()
		conf = config.conf()
		self.fileBtn.Enable(False)
		self.recordBtn.Enable(False)

		def work(cancel, progress):
			if translate:
				return self._cli.speech_to_text_translate(
					path, model=conf.get("sttTranslateModel"), cancel=cancel)
			language = None if lang in ("unknown", constants.AUTO_DETECT) else lang
			return self._cli.speech_to_text(
				path, language_code=language, model=conf.get("sttModel"), cancel=cancel)

		def ok(result):
			self.fileBtn.Enable(True)
			self.recordBtn.Enable(True)
			transcript = result.get("transcript", "")
			self.transcriptCtrl.SetValue(transcript)
			detected = result.get("language_code")
			if detected:
				common.report(_("Transcribed. Detected language {lang}").format(lang=detected))
			else:
				common.report(_("Transcribed"))

		def bad(exc):
			self.fileBtn.Enable(True)
			self.recordBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Speech to Text"),
			message=_("Transcribing audio..."), parent=self)

	def onCopy(self, evt):
		text = self.transcriptCtrl.GetValue()
		if not text:
			common.report(_("Nothing to copy"))
			return
		if wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			common.report(_("Copied"))

	def onSave(self, evt):
		text = self.transcriptCtrl.GetValue()
		if not text:
			common.report(_("Nothing to save"))
			return
		with wx.FileDialog(
				self, _("Save transcript"), defaultDir=common.default_output_folder(),
				defaultFile="transcript.txt",
				wildcard=_("Text files (*.txt)|*.txt"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write(text)
			common.report(_("Saved"))
		except Exception as e:
			common.error_dialog(self, e)

	def _onClose(self, evt):
		if self._rec.recording:
			self._rec.cancel()
		self.Destroy()
