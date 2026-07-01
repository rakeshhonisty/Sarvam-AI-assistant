# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Text to speech dialog."""

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
from .. import audioutils
from . import common

_player = audioutils.Player()


class TextToSpeechDialog(wx.Dialog):

	def __init__(self, parent, initial_text=""):
		# Translators: title of the text to speech dialog.
		super().__init__(parent, title=_("Sarvam AI - Text to Speech"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._wav = None
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: multiline text field holding the text to synthesise.
		self.textCtrl = helper.addLabeledControl(
			_("&Text to speak:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(560, 200))
		self.textCtrl.SetValue(initial_text or "")

		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		for label, handler in (
				(_("From se&lection"), self._fromSelection),
				(_("From cli&pboard"), self._fromClipboard),
				(_("Open te&xt file..."), self._fromFile)):
			b = srcBtns.addButton(self, label=label)
			b.Bind(wx.EVT_BUTTON, handler)
		helper.addItem(srcBtns)

		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.voiceCtrl = row.addLabeledControl(
			_("&Voice:"), wx.Choice, choices=list(constants.SPEAKERS_V2 + constants.SPEAKERS_V1))
		self._selectValue(self.voiceCtrl, conf.get("defaultSpeaker"))
		labels, self._langCodes = common.language_choices()
		self.langCtrl = row.addLabeledControl(_("La&nguage:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage"))
		helper.addItem(row.sizer)

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.speakBtn = btns.addButton(self, label=_("&Speak"))
		self.speakBtn.Bind(wx.EVT_BUTTON, self.onSpeak)
		self.saveBtn = btns.addButton(self, label=_("Sa&ve audio..."))
		self.saveBtn.Bind(wx.EVT_BUTTON, self.onSave)
		self.pauseBtn = btns.addButton(self, label=_("&Pause"))
		self.pauseBtn.Bind(wx.EVT_BUTTON, self.onPauseResume)
		self.stopBtn = btns.addButton(self, label=_("St&op"))
		self.stopBtn.Bind(wx.EVT_BUTTON, self.onStop)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self._updateButtons()
		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.textCtrl.SetFocus()

	# -- input sources ------------------------------------------------------
	def _fromSelection(self, evt):
		text = _get_selection()
		if text:
			self.textCtrl.SetValue(text)
			common.report(_("Selection loaded"))
		else:
			common.report(_("No selected text"))

	def _fromClipboard(self, evt):
		text = _get_clipboard_text()
		if text:
			self.textCtrl.SetValue(text)
			common.report(_("Clipboard loaded"))
		else:
			common.report(_("Clipboard has no text"))

	def _fromFile(self, evt):
		with wx.FileDialog(
				self, _("Open text file"),
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "r", encoding="utf-8", errors="replace") as f:
				self.textCtrl.SetValue(f.read())
			common.report(_("File loaded"))
		except Exception as e:
			common.error_dialog(self, e)

	# -- synthesis ----------------------------------------------------------
	def onSpeak(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text to speak"))
			return
		conf = config.conf()
		voice = self.voiceCtrl.GetStringSelection()
		lang = self._langCodes[self.langCtrl.GetSelection()]
		self.speakBtn.Enable(False)

		def work(cancel, progress):
			return self._cli.text_to_speech(
				text, language_code=lang, speaker=voice,
				model=conf.get("ttsModel"), pitch=conf.get("pitch"),
				pace=conf.get("pace"), loudness=conf.get("loudness"),
				sample_rate=conf.get("sampleRate"),
				enable_preprocessing=conf.get("enablePreprocessing"),
				cancel=cancel, progress=progress)

		def ok(wav):
			self.speakBtn.Enable(True)
			self._wav = wav
			self._updateButtons()
			if getattr(self, "_saveAfterSynth", False):
				self._saveAfterSynth = False
				self._doSave()
				return
			if config.conf().get("autoPlayTts"):
				_player.play(wav)
				common.report(_("Playing"))
			else:
				common.report(_("Audio ready"))

		def bad(exc):
			self.speakBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Text to Speech"),
			message=_("Synthesising speech..."), parent=self)

	def onSave(self, evt):
		if not self._wav:
			# Synthesise first, then save.
			common.report(_("Generating audio to save"))
			self._saveAfterSynth = True
			self.onSpeak(evt)
			return
		self._doSave()

	def _doSave(self):
		with wx.FileDialog(
				self, _("Save audio"), defaultDir=common.default_output_folder(),
				defaultFile="sarvam_tts.wav",
				wildcard=_("WAV audio (*.wav)|*.wav"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			audioutils.save_wav(self._wav, path)
			common.report(_("Audio saved"))
		except Exception as e:
			common.error_dialog(self, e)

	def onPauseResume(self, evt):
		if not _player.is_playing():
			if self._wav:
				_player.play(self._wav)
			return
		if _player.paused:
			_player.resume()
			common.report(_("Resumed"))
		else:
			_player.pause()
			common.report(_("Paused"))
		self._updateButtons()

	def onStop(self, evt):
		_player.stop()
		common.report(_("Stopped"))
		self._updateButtons()

	def _updateButtons(self):
		has = self._wav is not None
		self.saveBtn.Enable(True)
		self.pauseBtn.Enable(has)
		self.stopBtn.Enable(has)
		self.pauseBtn.SetLabel(_("&Resume") if _player.paused else _("&Pause"))

	def _selectValue(self, ctrl, value):
		items = [ctrl.GetString(i) for i in range(ctrl.GetCount())]
		if value in items:
			ctrl.SetSelection(items.index(value))
		elif items:
			ctrl.SetSelection(0)

	def _onClose(self, evt):
		_player.stop()
		self.Destroy()


# --- helpers shared by several dialogs --------------------------------------
def _get_selection():
	try:
		import api
		import textInfos
		obj = api.getFocusObject()
		info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
		if info and not info.isCollapsed:
			return info.text
	except Exception:
		pass
	return ""


def _get_clipboard_text():
	try:
		import api
		return api.getClipData()
	except Exception:
		return ""
