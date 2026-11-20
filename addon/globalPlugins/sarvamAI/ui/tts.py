# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Text to speech dialog.

Order: type or paste text (or upload almost any document - text, Word, EPUB,
HTML, RTF, PowerPoint, Excel, PDF, scans, even audio), then choose a voice in
four steps that narrow each other down:

    Voice model  ->  Language  ->  Gender  ->  Purpose (nature of work)  ->  Voice

Bulbul v4 Flash personas are made for a kind of work (news, narration,
customer support, education, ads, devotional ...) and a language; Bulbul v3
voices speak every language. The same Gender + Purpose classification picks
voices on both models. Tune Speed and Expression, press Convert, then Listen
or Download in MP3, WAV, FLAC or AAC.

Malayalam and Odia are not covered by Bulbul v4 Flash; the add-on switches to
the closest Bulbul v3 voice automatically and says so.
"""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import errors
from .. import tasks
from .. import audioutils
from .. import fileio
from .. import models
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
		self._wavKey = None
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Text (type or paste) + upload.
		self.textCtrl = helper.addLabeledControl(
			_("&Text to speak (type or paste):"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 160))
		self.textCtrl.SetValue(initial_text or "")
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Upload file (documents, PDF, images, audio)..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		helper.addItem(up)

		# 2) Voice model + language.
		row1 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._modelIds = list(models.tts_ids())
		self.modelCtrl = row1.addLabeledControl(
			_("Voice &model:"), wx.Choice,
			choices=[models.label_of("tts", m) for m in self._modelIds])
		common.select_in_combo(self.modelCtrl, self._modelIds, conf.get("ttsModel") or models.DEFAULT_TTS_MODEL)
		self.modelCtrl.Bind(wx.EVT_CHOICE, self._onModel)
		labels, self._langCodes = common.language_choices(include_auto=True)
		self.langCtrl = row1.addLabeledControl(_("&Language:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage") or constants.AUTO_DETECT)
		self.langCtrl.Bind(wx.EVT_CHOICE, self._onLanguage)
		helper.addItem(row1.sizer)

		# 3) Voice classification: gender -> purpose -> voice.
		row2 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.genderCtrl = row2.addLabeledControl(_("&Gender:"), wx.Choice,
			choices=[_("Female"), _("Male")])
		self._genders = list(ttsstyles.GENDERS)
		common.select_in_combo(self.genderCtrl, self._genders, conf.get("ttsGender") or "Female")
		self.genderCtrl.Bind(wx.EVT_CHOICE, self._onGender)
		# Translators: the nature of work / purpose a voice is made for.
		self.purposeCtrl = row2.addLabeledControl(_("&Purpose (nature of work):"), wx.Choice, choices=[])
		self.purposeCtrl.Bind(wx.EVT_CHOICE, self._onPurpose)
		helper.addItem(row2.sizer)
		self.voiceCtrl = helper.addLabeledControl(_("&Voice:"), wx.Choice, choices=[])
		self.voiceCtrl.Bind(wx.EVT_CHOICE, lambda e: self._invalidate())
		self._purposeKeys = []
		self._voiceIds = []

		# 4) Sliders (each names itself so NVDA announces its purpose).
		self.speedCtrl = self._slider(
			helper,
			# Translators: speed slider. 100 is normal speed.
			_("Speech s&peed in percent, 50 is slowest and 200 is fastest:"),
			50, 200, int(float(conf.get("pace") or 1.0) * 100),
			_("Speech speed in percent"))
		self.expressionCtrl = self._slider(
			helper,
			# Translators: expression slider. Low values sound monotonous.
			_("E&xpression in percent, 5 is flat and monotonous and 100 is most lively:"),
			5, 100, int(float(conf.get("ttsTemperature") or 0.8) * 100),
			_("Expression in percent"))

		# 5) Convert.
		conv = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.convertBtn = conv.addButton(self, label=_("&Convert"))
		self.convertBtn.Bind(wx.EVT_BUTTON, self.onConvert)
		helper.addItem(conv)

		# 6) Result actions - hidden until a successful conversion.
		res = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._resultBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.listenBtn = self._resultBtns.addButton(self, label=_("&Listen"))
		self.listenBtn.Bind(wx.EVT_BUTTON, self.onListen)
		self.stopBtn = self._resultBtns.addButton(self, label=_("St&op"))
		self.stopBtn.Bind(wx.EVT_BUTTON, self.onStop)
		res.addItem(self._resultBtns)
		self._audioFormats = [k for k, _l in constants.AUDIO_SAVE_FORMATS]
		self.audioFormatCtrl = res.addLabeledControl(
			_("Download f&ormat:"), wx.Choice,
			choices=[_(lab) for _k, lab in constants.AUDIO_SAVE_FORMATS])
		common.select_in_combo(self.audioFormatCtrl, self._audioFormats, conf.get("ttsCodec") or "mp3")
		dl = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.downloadBtn = dl.addButton(self, label=_("&Download audio..."))
		self.downloadBtn.Bind(wx.EVT_BUTTON, self.onDownload)
		res.addItem(dl)
		helper.addItem(res.sizer)
		self._resultControls = [self.listenBtn, self.stopBtn, self.audioFormatCtrl,
			self.downloadBtn]
		try:
			self._resultControls.append(self.audioFormatCtrl.GetPrevSibling())
		except Exception:
			pass
		self._showResults(False)

		# Close.
		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self, cleanup=self._cleanup)
		self._mainSizer = wx.BoxSizer(wx.VERTICAL)
		self._mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self._refreshPurposes(conf.get("ttsStyle"))
		self._refreshVoices(self._savedVoice())
		self.SetSizerAndFit(self._mainSizer)
		self.CentreOnScreen()
		self.textCtrl.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _slider(self, helper, label, lo, hi, value, name):
		"""Create a slider NVDA announces properly (nvdaControls'
		EnhancedInputSlider when available)."""
		sliderClass = wx.Slider
		try:
			from gui import nvdaControls
			sliderClass = nvdaControls.EnhancedInputSlider
		except Exception:
			pass
		ctrl = helper.addLabeledControl(
			label, sliderClass, minValue=lo, maxValue=hi, style=wx.SL_HORIZONTAL)
		ctrl.SetValue(max(lo, min(hi, value)))
		try:
			ctrl.SetLineSize(5)
			ctrl.SetPageSize(25)
		except Exception:
			pass
		try:
			ctrl.SetName(name)
		except Exception:
			pass
		ctrl.Bind(wx.EVT_SLIDER, lambda e: (self._invalidate(), e.Skip()))
		return ctrl

	def _model(self):
		return self._modelIds[max(0, self.modelCtrl.GetSelection())]

	def _gender(self):
		return self._genders[max(0, self.genderCtrl.GetSelection())]

	def _selectedLang(self):
		return self._langCodes[max(0, self.langCtrl.GetSelection())]

	def _purpose(self):
		if not self._purposeKeys:
			return ttsstyles.default_style()
		return self._purposeKeys[max(0, self.purposeCtrl.GetSelection())]

	def _voice(self):
		if not self._voiceIds:
			return ttsstyles.default_voice(self._gender(), self._purpose(), model=self._model())
		return self._voiceIds[max(0, self.voiceCtrl.GetSelection())]

	def _savedVoice(self):
		key = "ttsVoiceV4" if self._model() == ttsstyles.MODEL_V4 else "ttsVoiceV3"
		return config.conf().get(key) or None

	def _refreshPurposes(self, wanted=None):
		prev = wanted or (self._purpose() if self._purposeKeys else None)
		avail = ttsstyles.purposes_available(self._model(), self._gender(), self._selectedLang())
		if not avail:
			avail = ttsstyles.purposes_available(self._model(), None, None)
		self._purposeKeys = [k for k, _l, _n in avail]
		self.purposeCtrl.Set([
			# Translators: a purpose with its number of voices, e.g. "News (6 voices)".
			_("{label} ({n} voices)").format(label=_(lab), n=n) for _k, lab, n in avail])
		common.select_in_combo(self.purposeCtrl, self._purposeKeys,
			prev if prev in self._purposeKeys else ttsstyles.default_style())

	def _refreshVoices(self, wanted=None):
		prev = wanted or (self._voice() if self._voiceIds else None)
		self._voiceIds = ttsstyles.voices_for(
			self._gender(), self._purpose(), model=self._model(), language=self._selectedLang())
		self.voiceCtrl.Set([ttsstyles.voice_label(v) for v in self._voiceIds])
		common.select_in_combo(self.voiceCtrl, self._voiceIds,
			prev if prev in self._voiceIds else ttsstyles.default_voice(
				self._gender(), self._purpose(), model=self._model(), language=self._selectedLang()))
		self._invalidate()

	def _onModel(self, evt):
		self._refreshPurposes()
		self._refreshVoices(self._savedVoice())
		lang = self._selectedLang()
		msg = models.label_of("tts", self._model())
		if lang != constants.AUTO_DETECT and not models.tts_supports_language(self._model(), lang):
			msg += ". " + _("This model does not support {lang}; Bulbul v3 will be used for it.").format(
				lang=constants.language_name(lang))
		common.report(_("{n} voices. {msg}").format(n=len(self._voiceIds), msg=msg))

	def _onLanguage(self, evt):
		self._refreshPurposes()
		self._refreshVoices()
		common.report(_("{n} voices").format(n=len(self._voiceIds)))

	def _onGender(self, evt):
		self._refreshPurposes()
		self._refreshVoices()
		common.report(_("{n} voices").format(n=len(self._voiceIds)))

	def _onPurpose(self, evt):
		p = ttsstyles.style_params(self._purpose())
		self.speedCtrl.SetValue(int(p["pace"] * 100))
		self.expressionCtrl.SetValue(int(p["temperature"] * 100))
		self._refreshVoices()
		common.report(_("{n} voices. Speed and expression set for this purpose.").format(n=len(self._voiceIds)))

	def _invalidate(self):
		# Any voice/prosody change means the converted audio is stale.
		self._wavKey = None

	def _showResults(self, show):
		for b in self._resultControls:
			try:
				b.Show(show)
			except Exception:
				pass
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	def _cleanup(self):
		_player.stop()
		conf = config.conf()
		try:
			conf["ttsModel"] = self._model()
			conf["ttsGender"] = self._gender()
			conf["ttsStyle"] = self._purpose()
			conf["ttsVoiceV4" if self._model() == ttsstyles.MODEL_V4 else "ttsVoiceV3"] = self._voice()
		except Exception:
			pass

	# -- upload -------------------------------------------------------------
	def onUpload(self, evt):
		exts = fileio.all_extensions()
		with wx.FileDialog(self, _("Upload a file"),
				wildcard=fileio.wildcard(_("Supported files"), exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		conf = config.conf()

		def ok(text):
			self.textCtrl.ChangeValue(text)
			self._invalidate()
			common.report(_("File loaded, {n} characters").format(n=len(text)))
			self.textCtrl.SetFocus()

		tasks.run_task(lambda cancel, progress: fileio.read_any(path, self._cli, conf, cancel, progress),
			on_success=ok, on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"), message=_("Reading {name}...").format(name=os.path.basename(path)),
			parent=self)

	# -- convert / play / save ---------------------------------------------
	def _params(self):
		return dict(
			speaker=self._voice(),
			model=self._model(),
			pace=self.speedCtrl.GetValue() / 100.0,
			temperature=self.expressionCtrl.GetValue() / 100.0,
			sample_rate=config.conf().get("sampleRate"))

	def _resolveLang(self, sel_lang, text, cancel):
		if sel_lang and sel_lang != constants.AUTO_DETECT:
			return sel_lang
		try:
			detected = self._cli.detect_language(text, cancel=cancel).get("language_code")
		except errors.SarvamError:
			detected = None
		return constants.to_tts_language(detected)

	def _synth(self, text, codec, cancel, progress):
		params = self._params()
		lang = self._resolveLang(self._selectedLang(), text, cancel)
		audio = self._cli.text_to_speech(
			text, language_code=lang, output_audio_codec=codec,
			cancel=cancel, progress=progress, concurrency=common.batch_concurrency(), **params)
		return audio, self._cli.last_tts_note

	def onConvert(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text to convert"))
			return
		self.convertBtn.Enable(False)
		key = (text, repr(self._params()), self._selectedLang())

		def ok(result):
			wav, note = result
			self.convertBtn.Enable(True)
			self._wav = wav
			self._wavKey = key
			self._showResults(True)
			msg = _("Converted. Listen and Download are now available.")
			if note:
				msg = note + " " + msg
			if config.conf().get("autoPlayTts"):
				_player.play(wav)
			common.report(msg)
			self.listenBtn.SetFocus()

		def bad(exc):
			self.convertBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(lambda cancel, progress: self._synth(text, "wav", cancel, progress),
			on_success=ok, on_error=bad,
			title=_("Sarvam AI - Text to Speech"),
			message=_("Converting to speech..."), parent=self)

	def onListen(self, evt):
		if self._wav:
			_player.play(self._wav)
			common.report(_("Playing"))

	def onStop(self, evt):
		_player.stop()
		common.report(_("Stopped"))

	def onDownload(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			return
		fmt = self._audioFormats[max(0, self.audioFormatCtrl.GetSelection())]
		label = dict(constants.AUDIO_SAVE_FORMATS)[fmt]
		path = common.ask_save_path(self, "sarvam_tts." + fmt,
			"%s|*.%s" % (_(label), fmt), title=_("Save audio"))
		if not path:
			return
		if not path.lower().endswith("." + fmt):
			path += "." + fmt
		config.conf()["ttsCodec"] = fmt
		key = (text, repr(self._params()), self._selectedLang())
		if fmt == "wav" and self._wav and self._wavKey == key:
			try:
				audioutils.save_wav(self._wav, path)
				common.report(_("Saved {name}").format(name=os.path.basename(path)))
			except Exception as e:
				common.error_dialog(self, e)
			return
		self.downloadBtn.Enable(False)

		def work(cancel, progress):
			data, _note = self._synth(text, fmt, cancel, progress)
			with open(path, "wb") as f:
				f.write(data)
			return path

		def ok(_p):
			self.downloadBtn.Enable(True)
			common.report(_("Saved {name}").format(name=os.path.basename(path)))

		def bad(exc):
			self.downloadBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Text to Speech"),
			message=_("Creating the {fmt} file...").format(fmt=fmt.upper()), parent=self)


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
