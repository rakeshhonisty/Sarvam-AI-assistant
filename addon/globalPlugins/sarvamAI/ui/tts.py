# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Text to speech dialog.

Order: type or paste text (or upload a .txt/.docx/.epub file), choose a speaking
style, gender and (dynamically filtered) voice, a language, and tune the speed,
pitch and volume sliders. Press Convert. Only after a successful conversion do
the Listen and Save (MP3 / WAV) controls appear.
"""

import wx
import gui
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import errors
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
		self._wav = None
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Text (type or paste) + upload.
		self.textCtrl = helper.addLabeledControl(
			_("&Text to speak (type or paste):"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(580, 170))
		self.textCtrl.SetValue(initial_text or "")
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Upload file (text, Word, EPUB)..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		helper.addItem(up)

		# 2) Model / style / gender.
		row1 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.modelCtrl = row1.addLabeledControl(_("&Model:"), wx.Choice, choices=list(ttsstyles.MODELS))
		self._sel(self.modelCtrl, conf.get("ttsModel") or ttsstyles.DEFAULT_MODEL)
		self.modelCtrl.Bind(wx.EVT_CHOICE, self._refreshVoices)
		self._styleKeys = list(ttsstyles.style_keys())
		self.styleCtrl = row1.addLabeledControl(
			_("Speaking s&tyle:"), wx.Choice,
			choices=[ttsstyles.style_label(k) for k in self._styleKeys])
		common.select_in_combo(self.styleCtrl, self._styleKeys, conf.get("ttsStyle"))
		self.styleCtrl.Bind(wx.EVT_CHOICE, self._onStyle)
		self.genderCtrl = row1.addLabeledControl(_("&Gender:"), wx.Choice, choices=list(ttsstyles.GENDERS))
		self._sel(self.genderCtrl, conf.get("ttsGender") or "Female")
		self.genderCtrl.Bind(wx.EVT_CHOICE, self._refreshVoices)
		helper.addItem(row1.sizer)

		# 3) Voice (filtered) + language.
		row2 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.voiceCtrl = row2.addLabeledControl(_("&Voice:"), wx.Choice, choices=[])
		labels, self._langCodes = common.language_choices(include_auto=True)
		self.langCtrl = row2.addLabeledControl(_("&Language:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage") or constants.AUTO_DETECT)
		helper.addItem(row2.sizer)
		self._refreshVoices()

		# 4) Sliders (each names itself so NVDA announces its purpose).
		self.speedCtrl = self._slider(helper, _("Speech s&peed, percent:"), 30, 300,
			int(float(conf.get("pace") or 1.0) * 100), _("Speech speed percent"))
		self.pitchCtrl = self._slider(helper, _("Pi&tch:"), -75, 75,
			int(float(conf.get("pitch") or 0.0) * 100), _("Pitch"))
		self.volumeCtrl = self._slider(helper, _("Vol&ume, percent:"), 10, 300,
			int(float(conf.get("loudness") or 1.0) * 100), _("Volume percent"))
		self._temperature = float(conf.get("ttsTemperature") or 0.6)
		self._applyStyle(conf.get("ttsStyle") or ttsstyles.default_style(), sliders=True)

		# 5) Convert.
		conv = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.convertBtn = conv.addButton(self, label=_("&Convert"))
		self.convertBtn.Bind(wx.EVT_BUTTON, self.onConvert)
		helper.addItem(conv)

		# 6) Result actions - hidden until a successful conversion.
		self._resultBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.listenBtn = self._resultBtns.addButton(self, label=_("&Listen"))
		self.listenBtn.Bind(wx.EVT_BUTTON, self.onListen)
		self.stopBtn = self._resultBtns.addButton(self, label=_("St&op"))
		self.stopBtn.Bind(wx.EVT_BUTTON, self.onStop)
		self.mp3Btn = self._resultBtns.addButton(self, label=_("Save as &MP3..."))
		self.mp3Btn.Bind(wx.EVT_BUTTON, self.onSaveMp3)
		self.wavBtn = self._resultBtns.addButton(self, label=_("Save as &WAV..."))
		self.wavBtn.Bind(wx.EVT_BUTTON, self.onSaveWav)
		helper.addItem(self._resultBtns)
		self._showResults(False)

		# Close.
		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self, cleanup=lambda: _player.stop())
		self._mainSizer = wx.BoxSizer(wx.VERTICAL)
		self._mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(self._mainSizer)
		self.CentreOnScreen()
		self.textCtrl.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _sel(self, ctrl, value):
		items = [ctrl.GetString(i) for i in range(ctrl.GetCount())]
		ctrl.SetSelection(items.index(value) if value in items else 0)

	def _slider(self, helper, label, lo, hi, value, name):
		ctrl = helper.addLabeledControl(
			label, wx.Slider, minValue=lo, maxValue=hi,
			style=wx.SL_HORIZONTAL | wx.SL_LABELS)
		ctrl.SetValue(max(lo, min(hi, value)))
		try:
			ctrl.SetName(name)
		except Exception:
			pass
		return ctrl

	def _model(self):
		return self.modelCtrl.GetStringSelection() or ttsstyles.DEFAULT_MODEL

	def _gender(self):
		return self.genderCtrl.GetStringSelection() or "Female"

	def _styleKey(self):
		return self._styleKeys[self.styleCtrl.GetSelection()]

	def _refreshVoices(self, evt=None):
		prev = self.voiceCtrl.GetStringSelection()
		voices = ttsstyles.voices_for(self._model(), self._gender(), self._styleKey())
		self.voiceCtrl.Set(voices)
		if prev in voices:
			self.voiceCtrl.SetSelection(voices.index(prev))
		elif voices:
			self.voiceCtrl.SetSelection(0)

	def _onStyle(self, evt):
		self._applyStyle(self._styleKey(), sliders=True)
		self._refreshVoices()
		common.report(_("Style applied"))

	def _applyStyle(self, key, sliders=False):
		p = ttsstyles.style_params(key)
		self._temperature = p.get("temperature", 0.6)
		if sliders:
			self.speedCtrl.SetValue(int(p.get("pace", 1.0) * 100))
			self.pitchCtrl.SetValue(int(p.get("pitch", 0.0) * 100))
			self.volumeCtrl.SetValue(int(p.get("loudness", 1.0) * 100))

	def _showResults(self, show):
		for b in (self.listenBtn, self.stopBtn, self.mp3Btn, self.wavBtn):
			b.Show(show)
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	# -- upload -------------------------------------------------------------
	def onUpload(self, evt):
		exts = ";".join("*" + e for e in textextract.SUPPORTED_EXTENSIONS)
		with wx.FileDialog(self, _("Upload a document"),
				wildcard=_("Documents (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		tasks.run_task(lambda cancel, progress: textextract.extract_text(path),
			on_success=lambda t: (self.textCtrl.SetValue(t), common.report(_("File loaded")), self.textCtrl.SetFocus()),
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"), message=_("Reading document..."), parent=self)

	# -- convert / play / save ---------------------------------------------
	def _params(self):
		return dict(
			speaker=self.voiceCtrl.GetStringSelection() or None,
			model=self._model(),
			pitch=self.pitchCtrl.GetValue() / 100.0,
			pace=self.speedCtrl.GetValue() / 100.0,
			loudness=self.volumeCtrl.GetValue() / 100.0,
			temperature=self._temperature,
			sample_rate=config.conf().get("sampleRate"),
			enable_preprocessing=config.conf().get("enablePreprocessing"))

	def _selectedLang(self):
		return self._langCodes[self.langCtrl.GetSelection()]

	def _resolveLang(self, sel_lang, text, cancel):
		if sel_lang and sel_lang != constants.AUTO_DETECT:
			return sel_lang
		try:
			detected = self._cli.detect_language(text, cancel=cancel).get("language_code")
		except errors.SarvamError:
			detected = None
		return constants.to_tts_language(detected)

	def onConvert(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text to convert"))
			return
		params = self._params()
		sel_lang = self._selectedLang()
		self.convertBtn.Enable(False)

		def work(cancel, progress):
			lang = self._resolveLang(sel_lang, text, cancel)
			return self._cli.text_to_speech(
				text, language_code=lang, output_audio_codec="wav",
				cancel=cancel, progress=progress, **params)

		def ok(wav):
			self.convertBtn.Enable(True)
			self._wav = wav
			self._showResults(True)
			if config.conf().get("autoPlayTts"):
				_player.play(wav)
				common.report(_("Converted. Playing. Save options are now available."))
			else:
				common.report(_("Converted. Listen and Save options are now available."))
			self.listenBtn.SetFocus()

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

	def onStop(self, evt):
		_player.stop()
		common.report(_("Stopped"))

	def onSaveWav(self, evt):
		if not self._wav:
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
			return
		path = self._askSave("sarvam_tts.mp3", _("MP3 audio (*.mp3)|*.mp3"))
		if not path:
			return
		params = self._params()
		sel_lang = self._selectedLang()
		self.mp3Btn.Enable(False)

		def work(cancel, progress):
			lang = self._resolveLang(sel_lang, text, cancel)
			data = self._cli.text_to_speech(
				text, language_code=lang, output_audio_codec="mp3",
				cancel=cancel, progress=progress, **params)
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
		with wx.FileDialog(self, _("Save audio"), defaultDir=common.default_output_folder(),
				defaultFile=default_name, wildcard=wildcard,
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			return fd.GetPath() if fd.ShowModal() == wx.ID_OK else None


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
