# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""A focused, standalone setup dialog for the API key and core defaults.

This complements the full settings category (Preferences > Settings > Sarvam
AI). It is deliberately simple and, importantly, does NOT close when Enter is
pressed in the key field - Enter validates the key instead. Nothing is saved
until you press Save."""

import wx
import gui
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import logger
from . import common


class SetupDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the quick setup dialog.
		super().__init__(parent, title=_("Sarvam AI - Setup"))
		self._cli = client.SarvamClient(config)
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		intro = wx.StaticText(self, label=_(
			"Enter your Sarvam API key below. Get a key (with credits) from "
			"https://dashboard.sarvam.ai. Press Enter in the key box to test it."))
		helper.addItem(intro)

		# API key (Enter validates, does not close the dialog).
		self.apiKeyCtrl = helper.addLabeledControl(
			_("Sarvam API &key:"), wx.TextCtrl, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
		self.apiKeyCtrl.SetValue(config.getApiKey())
		self.apiKeyCtrl.Bind(wx.EVT_TEXT_ENTER, self.onValidate)

		keyBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.validateBtn = keyBtns.addButton(self, label=_("&Validate key / Test connection"))
		self.validateBtn.Bind(wx.EVT_BUTTON, self.onValidate)
		self.showBtn = keyBtns.addButton(self, label=_("Sho&w key"))
		self.showBtn.Bind(wx.EVT_BUTTON, self.onShowKey)
		helper.addItem(keyBtns)

		# Base URL (advanced).
		self.baseUrlCtrl = helper.addLabeledControl(
			_("API &base URL:"), wx.TextCtrl, style=wx.TE_PROCESS_ENTER)
		self.baseUrlCtrl.SetValue(conf.get("baseUrl") or constants.DEFAULT_BASE_URL)
		self.baseUrlCtrl.Bind(wx.EVT_TEXT_ENTER, self.onValidate)

		# A couple of core defaults for convenience.
		labels, self._langCodes = common.language_choices()
		self.langCtrl = helper.addLabeledControl(_("Default &language:"), wx.Choice, choices=labels)
		common.select_in_combo(self.langCtrl, self._langCodes, conf.get("defaultLanguage"))
		self.modelCtrl = helper.addLabeledControl(
			_("Default TTS &model:"), wx.Choice, choices=list(constants.TTS_MODELS))
		common.select_in_combo(self.modelCtrl, list(constants.TTS_MODELS), conf.get("ttsModel"))

		# Save / full settings / cancel. None of these is the Enter default, so
		# pressing Enter never closes the dialog unexpectedly.
		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.saveBtn = btns.addButton(self, label=_("&Save"))
		self.saveBtn.Bind(wx.EVT_BUTTON, self.onSave)
		self.fullBtn = btns.addButton(self, label=_("Advanced se&ttings..."))
		self.fullBtn.Bind(wx.EVT_BUTTON, self.onFull)
		cancelBtn = btns.addButton(self, id=wx.ID_CANCEL, label=_("Cancel"))
		cancelBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CANCEL)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.apiKeyCtrl.SetFocus()

	def onShowKey(self, evt):
		key = self.apiKeyCtrl.GetValue()
		if not key:
			common.report(_("No key entered"))
			return
		gui.messageBox(key, _("Sarvam API key"), wx.OK | wx.ICON_INFORMATION, self)

	def onValidate(self, evt=None):
		# Persist the typed key/URL so the test uses them, without closing.
		config.setApiKey(self.apiKeyCtrl.GetValue())
		config.conf()["baseUrl"] = self.baseUrlCtrl.GetValue().strip() or constants.DEFAULT_BASE_URL
		self.validateBtn.Enable(False)
		cli = client.SarvamClient(config)

		def ok(result):
			self.validateBtn.Enable(True)
			gui.messageBox(result, _("Sarvam AI - Connection"), wx.OK | wx.ICON_INFORMATION, self)

		def bad(exc):
			self.validateBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(lambda cancel, progress: cli.test_connection(cancel=cancel),
			on_success=ok, on_error=bad, title=_("Sarvam AI"),
			message=_("Testing connection..."), parent=self)

	def onSave(self, evt):
		conf = config.conf()
		config.setApiKey(self.apiKeyCtrl.GetValue())
		conf["baseUrl"] = self.baseUrlCtrl.GetValue().strip() or constants.DEFAULT_BASE_URL
		conf["defaultLanguage"] = self._langCodes[self.langCtrl.GetSelection()]
		conf["ttsModel"] = list(constants.TTS_MODELS)[self.modelCtrl.GetSelection()]
		logger.info("Setup saved from quick dialog.")
		common.report(_("Saved"))
		self.Close()

	def onFull(self, evt):
		from .settings import SarvamSettingsPanel
		wx.CallAfter(gui.mainFrame.popupSettingsDialog,
			gui.settingsDialogs.NVDASettingsDialog, SarvamSettingsPanel)
