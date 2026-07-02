# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Text to speech dialog.

Workflow: type or paste text (or upload a .txt/.docx/.epub file), choose the
model, conversion style, gender, voice and language, tune speed and pitch, then
press Convert. After conversion you can Listen, or save the audio as MP3 or WAV.
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
from .. import audioutils
from .. import textextract
from .. import ttsstyles
from . import common

_player = audioutils.Player()


class TextToSpeechDialog(wx.Dialog):

	def __init__(self, parent, initial_text=""):
		# Translators: title of the text to speech dialog.
		super().__init__(parent, title=_("Sarvam AI - Text to Speech"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._wav = None  # last converted WAV bytes (for playback / WAV save)
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Text box (paste target) + upload.
		self.textCtrl = helper.addLabeledControl(
			_("&Text to speak (type, paste, or upload a file):"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(580, 180))
		self.textCtrl.SetValue(initial_text or "")

		uploadRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = uploadRow.addButton(
			self, label=_("&Upload file (text, Word, EPUB)..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		helper.addItem(uploadRow)

		# Model / style / gender.
		row1 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.modelCtrl = row1.addLabeledControl(
			_("&Model:"), wx.Choice, choices=list(ttsstyles.MODELS))
		self._select(self.modelCtrl, conf.get("ttsModel") or ttsstyles.DEFAULT_MODEL)
		self.modelCtrl.Bind(wx.EVT_CHOICE, self._onModelOrGender)
		self._styleKeys = list(ttsstyles.style_keys())
		self.styleCtrl = row1.addLabeledControl(
			_("Conversion s&tyle:"), wx.Choice,
			choices=[ttsstyles.style_label(k) for k in self._styleKeys])
		self._select(self.styleCtrl, ttsstyles.style_label(conf.get("ttsStyle") or "neutral"))
		self.styleCtrl.Bind(wx.EVT_CHOICE, self._onStyle)
		self.genderCtrl = row1.addLabeledControl(
			_("&Gender:"), wx.Choice, choices=list(ttsstyles.GENDERS))
		self._select(self.genderCtrl, conf.get("ttsGender") or "Any")
		self.genderCtrl.Bind(wx.EVT_CHOICE, self._onModelOrGender)
		helper.addItem(row1.sizer)

		# Voice / language.
		row2 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.voiceCtrl = row2.addLabeledControl(_("&Voice:"), wx.Choice, choices=[])
		labels, self._langCodes = common.language_choices()
		self.langCtrl = row2.addLabeledControl(_("&Language:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage"))
		helper.addItem(row2.sizer)
		self._reloadVoices(conf.get("defaultSpeaker"))

		# Speed + pitch sliders (mapped: slider value / 100).
		self.speedCtrl, self.speedLabel = self._slider(
			helper, _("&Speed:"), 30, 300, int(float(conf.get("pace") or 1.0) * 100))
		self.pitchCtrl, self.pitchLabel = self._slider(
			helper, _("&Pitch:"), -75, 75, int(float(conf.get("pitch") or 0.0) * 100))
		# Hidden style-driven parameters (not shown as sliders).
		self._temperature = float(conf.get("ttsTemperature") or 0.6)
		self._loudness = float(conf.get("loudness") or 1.0)
		self._applyStyle(conf.get("ttsStyle") or "neutral", updateSliders=True)

		# Actions.
		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.convertBtn = btns.addButton(self, label=_("&Convert"))
		self.convertBtn.Bind(wx.EVT_BUTTON, self.onConvert)
		self.listenBtn = btns.addButton(self, label=_("&Listen"))
		self.listenBtn.Bind(wx.EVT_BUTTON, self.onListen)
		self.stopBtn = btns.addButton(self, label=_("St&op"))
		self.stopBtn.Bind(wx.EVT_BUTTON, self.onStop)
		self.mp3Btn = btns.addButton(self, label=_("Save as &MP3..."))
		self.mp3Btn.Bind(wx.EVT_BUTTON, self.onSaveMp3)
		self.wavBtn = btns.addButton(self, label=_("Save as &WAV..."))
		self.wavBtn.Bind(wx.EVT_BUTTON, self.onSaveWav)
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

	# -- small helpers ------------------------------------------------------
	def _select(self, ctrl, value):
		items = [ctrl.GetString(i) for i in range(ctrl.GetCount())]
		if value in items:
			ctrl.SetSelection(items.index(value))
		elif items:
			ctrl.SetSelection(0)

	def _slider(self, helper, label, lo, hi, value):
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		ctrl = row.addLabeledControl(
			label, wx.Slider, minValue=lo, maxValue=hi,
			style=wx.SL_HORIZONTAL | wx.SL_LABELS)
		ctrl.SetValue(max(lo, min(hi, value)))
		readout = row.addItem(wx.StaticText(self, label=self._fmt(ctrl.GetValue())))
		ctrl.Bind(wx.EVT_SLIDER, lambda e, c=ctrl, r=readout: r.SetLabel(self._fmt(c.GetValue())))
		helper.addItem(row.sizer)
		return ctrl, readout

	def _fmt(self, v):
		return "%.2f" % (v / 100.0)

	def _model(self):
		return self.modelCtrl.GetStringSelection() or ttsstyles.DEFAULT_MODEL

	def _gender(self):
		return self.genderCtrl.GetStringSelection() or "Any"

	def _reloadVoices(self, preferred=None):
		voices = ttsstyles.speakers_for(self._model(), self._gender())
		self.voiceCtrl.Set(voices)
		if preferred and preferred in voices:
			self.voiceCtrl.SetSelection(voices.index(preferred))
		elif voices:
			self.voiceCtrl.SetSelection(0)

	def _onModelOrGender(self, evt):
		self._reloadVoices(self.voiceCtrl.GetStringSelection())

	def _onStyle(self, evt):
		self._applyStyle(self._styleKeys[self.styleCtrl.GetSelection()], updateSliders=True)
		common.report(_("Style applied"))

	def _applyStyle(self, key, updateSliders=False):
		p = ttsstyles.style_params(key)
		self._temperature = p.get("temperature", 0.6)
		self._loudness = p.get("loudness", 1.0)
		if updateSliders:
			self.speedCtrl.SetValue(int(p.get("pace", 1.0) * 100))
			self.pitchCtrl.SetValue(int(p.get("pitch", 0.0) * 100))
			self.speedLabel.SetLabel(self._fmt(self.speedCtrl.GetValue()))
			self.pitchLabel.SetLabel(self._fmt(self.pitchCtrl.GetValue()))

	# -- upload -------------------------------------------------------------
	def onUpload(self, evt):
		exts = ";".join("*" + e for e in textextract.SUPPORTED_EXTENSIONS)
		with wx.FileDialog(
				self, _("Upload a document"),
				wildcard=_("Documents (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()

		def work(cancel, progress):
			return textextract.extract_text(path)

		def ok(text):
			self.textCtrl.SetValue(text)
			common.report(_("File loaded: {n} characters").format(n=len(text)))
			self.textCtrl.SetFocus()

		tasks.run_task(work, on_success=ok,
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"), message=_("Reading document..."), parent=self)

	# -- convert / play / save ---------------------------------------------
	def _params(self):
		return dict(
			language_code=self._langCodes[self.langCtrl.GetSelection()],
			speaker=self.voiceCtrl.GetStringSelection() or None,
			model=self._model(),
			pitch=self.pitchCtrl.GetValue() / 100.0,
			pace=self.speedCtrl.GetValue() / 100.0,
			loudness=self._loudness,
			temperature=self._temperature,
			sample_rate=config.conf().get("sampleRate"),
			enable_preprocessing=config.conf().get("enablePreprocessing"))

	def onConvert(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text to convert"))
			return
		params = self._params()
		self.convertBtn.Enable(False)

		def work(cancel, progress):
			return self._cli.text_to_speech(
				text, output_audio_codec="wav", cancel=cancel, progress=progress, **params)

		def ok(wav):
			self.convertBtn.Enable(True)
			self._wav = wav
			self._updateButtons()
			if config.conf().get("autoPlayTts"):
				_player.play(wav)
				common.report(_("Converted. Playing."))
			else:
				common.report(_("Converted. Press Listen to play."))

		def bad(exc):
			self.convertBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Text to Speech"),
			message=_("Converting to speech..."), parent=self)

	def onListen(self, evt):
		if self._wav:
			_player.play(self._wav)
			common.report(_("Playing"))
		else:
			common.report(_("Convert first"))

	def onStop(self, evt):
		_player.stop()
		common.report(_("Stopped"))

	def onSaveWav(self, evt):
		if not self._wav:
			common.report(_("Convert first"))
			return
		path = self._askSave("sarvam_tts.wav", _("WAV audio (*.wav)|*.wav"))
		if not path:
			return
		try:
			audioutils.save_wav(self._wav, path)
			common.report(_("WAV saved"))
		except Exception as e:
			common.error_dialog(self, e)

	def onSaveMp3(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text to convert"))
			return
		path = self._askSave("sarvam_tts.mp3", _("MP3 audio (*.mp3)|*.mp3"))
		if not path:
			return
		params = self._params()
		self.mp3Btn.Enable(False)

		def work(cancel, progress):
			data = self._cli.text_to_speech(
				text, output_audio_codec="mp3", cancel=cancel, progress=progress, **params)
			with open(path, "wb") as f:
				f.write(data)
			return path

		def ok(_p):
			self.mp3Btn.Enable(True)
			common.report(_("MP3 saved"))

		def bad(exc):
			self.mp3Btn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Text to Speech"),
			message=_("Generating MP3..."), parent=self)

	def _askSave(self, default_name, wildcard):
		with wx.FileDialog(
				self, _("Save audio"), defaultDir=common.default_output_folder(),
				defaultFile=default_name, wildcard=wildcard,
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			return fd.GetPath() if fd.ShowModal() == wx.ID_OK else None

	def _updateButtons(self):
		has = self._wav is not None
		self.listenBtn.Enable(has)
		self.stopBtn.Enable(has)
		self.wavBtn.Enable(has)
		self.mp3Btn.Enable(True)

	def _onClose(self, evt):
		_player.stop()
		self.Destroy()


# --- helpers still used by other modules (selection/clipboard readers) ------
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
