# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""The Sarvam AI settings category, shown inside NVDA's main Settings dialog."""

import os

import wx
import gui
import addonHandler
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import logger
from .. import ttsstyles
from . import common


class SarvamSettingsPanel(SettingsPanel):
	# Translators: the title of the Sarvam AI settings category.
	title = _("Sarvam AI")

	def makeSettings(self, settingsSizer):
		conf = config.conf()
		sh = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# --- Credentials ---------------------------------------------------
		# Translators: label for the API key field.
		self.apiKeyCtrl = sh.addLabeledControl(
			_("Sarvam API &key:"), wx.TextCtrl, style=wx.TE_PASSWORD)
		self.apiKeyCtrl.SetValue(config.getApiKey())

		keyBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.validateBtn = keyBtns.addButton(self, label=_("&Validate key / Test connection"))
		self.validateBtn.Bind(wx.EVT_BUTTON, self.onTestConnection)
		self.showKeyBtn = keyBtns.addButton(self, label=_("Sho&w key"))
		self.showKeyBtn.Bind(wx.EVT_BUTTON, self.onShowKey)
		sh.addItem(keyBtns)

		# Translators: label for the API base URL (advanced) field.
		self.baseUrlCtrl = sh.addLabeledControl(_("API &base URL:"), wx.TextCtrl)
		self.baseUrlCtrl.SetValue(conf.get("baseUrl") or constants.DEFAULT_BASE_URL)

		# --- Text to speech ------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("Text to speech")))
		self.ttsModelCtrl = self._choice(sh, _("TTS &model:"), constants.TTS_MODELS, conf.get("ttsModel"))
		_allVoices = tuple(ttsstyles.speakers_for("bulbul:v3", "Any")) + tuple(ttsstyles.speakers_for("bulbul:v2", "Any"))
		self.speakerCtrl = self._choice(sh, _("Default &voice:"), _allVoices, conf.get("defaultSpeaker"))
		labels, self._langCodes = common.language_choices(include_auto=True)
		# Translators: default synthesis language ("Auto detect" detects the
		# language of the text, including code-mixed text, before synthesis).
		self.langCtrl = sh.addLabeledControl(_("Default &language:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage") or constants.AUTO_DETECT)

		self.pitchCtrl = self._spin_float(sh, _("&Pitch (-0.75 to 0.75):"), conf.get("pitch"), constants.PITCH_RANGE)
		self.paceCtrl = self._spin_float(sh, _("Pac&e (0.3 to 3.0):"), conf.get("pace"), constants.PACE_RANGE)
		self.loudnessCtrl = self._spin_float(sh, _("&Loudness (0.1 to 3.0):"), conf.get("loudness"), constants.LOUDNESS_RANGE)
		self.sampleRateCtrl = self._choice(
			sh, _("Sample &rate:"), [str(r) for r in constants.TTS_SAMPLE_RATES], str(conf.get("sampleRate")))
		# Translators: checkbox to enable text preprocessing before synthesis.
		self.preprocCtrl = sh.addItem(wx.CheckBox(self, label=_("Enable text &preprocessing")))
		self.preprocCtrl.SetValue(bool(conf.get("enablePreprocessing")))
		# Translators: checkbox to play synthesised audio automatically.
		self.autoPlayCtrl = sh.addItem(wx.CheckBox(self, label=_("&Play audio automatically after synthesis")))
		self.autoPlayCtrl.SetValue(bool(conf.get("autoPlayTts")))

		# --- Speech to text ------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("Speech to text")))
		self.sttModelCtrl = self._choice(sh, _("STT mo&del:"), constants.STT_MODELS, conf.get("sttModel"))
		self.sttTransModelCtrl = self._choice(sh, _("Speech &translate model:"), constants.STT_TRANSLATE_MODELS, conf.get("sttTranslateModel"))

		# --- Translation ---------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("Translation")))
		self.translateModelCtrl = self._choice(sh, _("Translatio&n model:"), constants.TRANSLATE_MODELS, conf.get("translateModel"))
		srcLabels, self._srcCodes = common.language_choices(include_auto=True)
		self.translateSrcCtrl = sh.addLabeledControl(_("Default so&urce language:"), wx.Choice, choices=srcLabels)
		common.select_in_combo(self.translateSrcCtrl, self._srcCodes, conf.get("translateSourceLang"))
		tgtLabels, self._tgtCodes = common.language_choices()
		self.translateTgtCtrl = sh.addLabeledControl(_("Default targe&t language:"), wx.Choice, choices=tgtLabels)
		common.select_in_combo(self.translateTgtCtrl, self._tgtCodes, conf.get("translateTargetLang"))
		self.translateModeCtrl = self._choice(sh, _("Translation st&yle:"), constants.TRANSLATE_MODES, conf.get("translateMode"))

		# --- Chat ----------------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("AI chat and summarisation")))
		self.chatModelCtrl = self._choice(sh, _("&Chat model:"), constants.CHAT_MODELS, conf.get("chatModel"))

		# --- OCR -----------------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("OCR")))
		self.ocrEngineCtrl = self._choice(
			sh, _("Default OCR en&gine:"),
			[constants.OCR_ENGINE_SARVAM, constants.OCR_ENGINE_WINDOWS], conf.get("ocrEngine"))
		self._ocrLangCodes = list(constants.OCR_LANGUAGES.keys())
		ocrLangLabels = ["%s (%s)" % (name, code) for code, name in constants.OCR_LANGUAGES.items()]
		self.ocrLangCtrl = sh.addLabeledControl(_("Default OCR l&anguage:"), wx.Choice, choices=ocrLangLabels)
		common.select_in_combo(self.ocrLangCtrl, self._ocrLangCodes, conf.get("ocrLanguage"))
		self.ocrFormatCtrl = self._choice(
			sh, _("OCR output for&mat:"), constants.OCR_OUTPUT_FORMATS, conf.get("ocrOutputFormat"))

		# --- Folders -------------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("Folders")))
		self.outputFolderCtrl, outBrowse = self._folder(sh, _("&Output folder:"), conf.get("outputFolder"))
		outBrowse.Bind(wx.EVT_BUTTON, lambda e: self._browseFolder(self.outputFolderCtrl))
		self.downloadFolderCtrl, dlBrowse = self._folder(sh, _("Do&wnload folder:"), conf.get("downloadFolder"))
		dlBrowse.Bind(wx.EVT_BUTTON, lambda e: self._browseFolder(self.downloadFolderCtrl))

		# --- Advanced ------------------------------------------------------
		sh.addItem(wx.StaticText(self, label=_("Advanced")))
		# Translators: checkbox to prefer streaming APIs where available.
		self.streamingCtrl = sh.addItem(wx.CheckBox(self, label=_("Enable &streaming where supported")))
		self.streamingCtrl.SetValue(bool(conf.get("streaming")))
		self.timeoutCtrl = self._spin_int(sh, _("Network t&imeout (seconds):"), conf.get("networkTimeout"), 5, 600)
		self.retriesCtrl = self._spin_int(sh, _("Max &retries:"), conf.get("maxRetries"), 0, 10)
		# Translators: proxy URL field.
		self.proxyCtrl = sh.addLabeledControl(_("Pro&xy URL (optional):"), wx.TextCtrl)
		self.proxyCtrl.SetValue(conf.get("proxyUrl") or "")
		# Translators: checkbox enabling verbose debug logging.
		self.debugCtrl = sh.addItem(wx.CheckBox(self, label=_("Enable &debug logging")))
		self.debugCtrl.SetValue(bool(conf.get("debugLogging")))
		# Translators: checkbox enabling update checks.
		self.updatesCtrl = sh.addItem(wx.CheckBox(self, label=_("Check for &add-on updates")))
		self.updatesCtrl.SetValue(bool(conf.get("checkForUpdates")))

		restore = sh.addItem(wx.Button(self, label=_("Restore &defaults")))
		restore.Bind(wx.EVT_BUTTON, self.onRestoreDefaults)

	# -- helpers ------------------------------------------------------------
	def _choice(self, sh, label, values, current):
		values = list(values)
		ctrl = sh.addLabeledControl(label, wx.Choice, choices=values)
		if current in values:
			ctrl.SetSelection(values.index(current))
		elif values:
			ctrl.SetSelection(0)
		ctrl._values = values
		return ctrl

	def _spin_int(self, sh, label, current, lo, hi):
		ctrl = sh.addLabeledControl(label, wx.SpinCtrl, min=lo, max=hi)
		try:
			ctrl.SetValue(int(current))
		except Exception:
			ctrl.SetValue(lo)
		return ctrl

	def _spin_float(self, sh, label, current, rng):
		lo, hi = rng
		ctrl = sh.addLabeledControl(
			label, wx.SpinCtrlDouble, min=float(lo), max=float(hi), inc=0.05)
		try:
			ctrl.SetValue(float(current))
		except Exception:
			ctrl.SetValue(float(lo))
		ctrl.SetDigits(2)
		return ctrl

	def _folder(self, sh, label, current):
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		ctrl = row.addLabeledControl(label, wx.TextCtrl)
		ctrl.SetValue(current or "")
		btn = row.addItem(wx.Button(self, label=_("&Browse...")))
		sh.addItem(row.sizer)
		return ctrl, btn

	def _browseFolder(self, ctrl):
		with wx.DirDialog(self, _("Choose a folder"), defaultPath=ctrl.GetValue() or "") as dd:
			if dd.ShowModal() == wx.ID_OK:
				ctrl.SetValue(dd.GetPath())

	# -- button handlers ----------------------------------------------------
	def onShowKey(self, evt):
		# Toggle visibility by swapping the control style is awkward in wx;
		# instead reveal the current text in a read-only message.
		key = self.apiKeyCtrl.GetValue()
		if not key:
			common.report(_("No key entered"))
			return
		gui.messageBox(key, _("Sarvam API key"), wx.OK | wx.ICON_INFORMATION, self)

	def onTestConnection(self, evt):
		# Persist the currently typed key/URL first so the test uses them.
		config.setApiKey(self.apiKeyCtrl.GetValue())
		config.conf()["baseUrl"] = self.baseUrlCtrl.GetValue().strip() or constants.DEFAULT_BASE_URL
		self.validateBtn.Enable(False)
		cli = client.SarvamClient(config)

		def work(cancel, progress):
			return cli.test_connection(cancel=cancel)

		def ok(result):
			self.validateBtn.Enable(True)
			gui.messageBox(result, _("Sarvam AI - Connection"), wx.OK | wx.ICON_INFORMATION, self)

		def bad(exc):
			self.validateBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI"), message=_("Testing connection..."), parent=self)

	def onRestoreDefaults(self, evt):
		if gui.messageBox(
				_("Restore all Sarvam AI settings to their defaults? Your API key will be kept."),
				_("Restore defaults"), wx.YES | wx.NO | wx.ICON_QUESTION, self) != wx.YES:
			return
		key = config.getApiKey()
		config.restoreDefaults()
		config.setApiKey(key)
		# Rebuild the panel to reflect defaults.
		gui.messageBox(
			_("Defaults restored. Close and reopen this dialog to see all changes."),
			_("Restore defaults"), wx.OK | wx.ICON_INFORMATION, self)

	# -- persistence --------------------------------------------------------
	def isValid(self):
		url = self.baseUrlCtrl.GetValue().strip()
		if url and not (url.startswith("http://") or url.startswith("https://")):
			gui.messageBox(
				_("The API base URL must start with http:// or https://."),
				_("Invalid setting"), wx.OK | wx.ICON_ERROR, self)
			return False
		for label, ctrl in ((_("output"), self.outputFolderCtrl), (_("download"), self.downloadFolderCtrl)):
			val = ctrl.GetValue().strip()
			if val and not os.path.isdir(val):
				gui.messageBox(
					_("The {which} folder does not exist:\n{path}").format(which=label, path=val),
					_("Invalid setting"), wx.OK | wx.ICON_ERROR, self)
				return False
		return True

	def onSave(self):
		conf = config.conf()
		config.setApiKey(self.apiKeyCtrl.GetValue())
		conf["baseUrl"] = self.baseUrlCtrl.GetValue().strip() or constants.DEFAULT_BASE_URL
		conf["ttsModel"] = self.ttsModelCtrl._values[self.ttsModelCtrl.GetSelection()]
		conf["defaultSpeaker"] = self.speakerCtrl._values[self.speakerCtrl.GetSelection()]
		conf["defaultLanguage"] = self._langCodes[self.langCtrl.GetSelection()]
		conf["pitch"] = float(self.pitchCtrl.GetValue())
		conf["pace"] = float(self.paceCtrl.GetValue())
		conf["loudness"] = float(self.loudnessCtrl.GetValue())
		conf["sampleRate"] = int(self.sampleRateCtrl._values[self.sampleRateCtrl.GetSelection()])
		conf["enablePreprocessing"] = self.preprocCtrl.GetValue()
		conf["autoPlayTts"] = self.autoPlayCtrl.GetValue()
		conf["sttModel"] = self.sttModelCtrl._values[self.sttModelCtrl.GetSelection()]
		conf["sttTranslateModel"] = self.sttTransModelCtrl._values[self.sttTransModelCtrl.GetSelection()]
		conf["translateModel"] = self.translateModelCtrl._values[self.translateModelCtrl.GetSelection()]
		conf["translateSourceLang"] = self._srcCodes[self.translateSrcCtrl.GetSelection()]
		conf["translateTargetLang"] = self._tgtCodes[self.translateTgtCtrl.GetSelection()]
		conf["translateMode"] = self.translateModeCtrl._values[self.translateModeCtrl.GetSelection()]
		conf["chatModel"] = self.chatModelCtrl._values[self.chatModelCtrl.GetSelection()]
		conf["ocrEngine"] = self.ocrEngineCtrl._values[self.ocrEngineCtrl.GetSelection()]
		conf["ocrLanguage"] = self._ocrLangCodes[self.ocrLangCtrl.GetSelection()]
		conf["ocrOutputFormat"] = self.ocrFormatCtrl._values[self.ocrFormatCtrl.GetSelection()]
		conf["outputFolder"] = self.outputFolderCtrl.GetValue().strip()
		conf["downloadFolder"] = self.downloadFolderCtrl.GetValue().strip()
		conf["streaming"] = self.streamingCtrl.GetValue()
		conf["networkTimeout"] = int(self.timeoutCtrl.GetValue())
		conf["maxRetries"] = int(self.retriesCtrl.GetValue())
		conf["proxyUrl"] = self.proxyCtrl.GetValue().strip()
		conf["debugLogging"] = self.debugCtrl.GetValue()
		conf["checkForUpdates"] = self.updatesCtrl.GetValue()
		logger.setDebug(conf["debugLogging"])
		logger.info("Settings saved.")
