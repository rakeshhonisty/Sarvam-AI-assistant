# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Translation, transliteration and language detection dialog."""

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from . import common
from .tts import _get_selection, _get_clipboard_text


class TranslateDialog(wx.Dialog):

	OP_TRANSLATE = 0
	OP_TRANSLITERATE = 1
	OP_DETECT = 2

	def __init__(self, parent, initial_text="", operation=0):
		# Translators: title of the translation dialog.
		super().__init__(parent, title=_("Sarvam AI - Translate"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		conf = config.conf()

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: chooses translate / transliterate / detect language.
		self.opCtrl = helper.addLabeledControl(
			_("&Operation:"), wx.Choice,
			choices=[_("Translate"), _("Transliterate"), _("Detect language")])
		self.opCtrl.SetSelection(operation)
		self.opCtrl.Bind(wx.EVT_CHOICE, self._onOpChange)

		self.inputCtrl = helper.addLabeledControl(
			_("&Input text:"), wx.TextCtrl, style=wx.TE_MULTILINE, size=(560, 160))
		self.inputCtrl.SetValue(initial_text or "")

		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		b1 = srcBtns.addButton(self, label=_("From se&lection"))
		b1.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_selection()))
		b2 = srcBtns.addButton(self, label=_("From cli&pboard"))
		b2.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_clipboard_text()))
		helper.addItem(srcBtns)

		langRow = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		srcLabels, self._srcCodes = common.language_choices(include_auto=True)
		self.srcCtrl = langRow.addLabeledControl(_("&Source:"), wx.Choice, choices=srcLabels)
		common.select_in_combo(self.srcCtrl, self._srcCodes, conf.get("translateSourceLang"))
		tgtLabels, self._tgtCodes = common.language_choices()
		self.tgtCtrl = langRow.addLabeledControl(_("&Target:"), wx.Choice, choices=tgtLabels)
		common.select_in_combo(self.tgtCtrl, self._tgtCodes, conf.get("translateTargetLang"))
		helper.addItem(langRow.sizer)

		self.modeCtrl = helper.addLabeledControl(
			_("Translation st&yle:"), wx.Choice, choices=list(constants.TRANSLATE_MODES))
		common.select_in_combo(self.modeCtrl, list(constants.TRANSLATE_MODES), conf.get("translateMode"))

		self.outputCtrl = helper.addLabeledControl(
			_("&Result:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(560, 160))

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.goBtn = btns.addButton(self, label=_("&Go"))
		self.goBtn.Bind(wx.EVT_BUTTON, self.onGo)
		self.copyBtn = btns.addButton(self, label=_("&Copy result"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		self._onOpChange(None)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.inputCtrl.SetFocus()

	def _load(self, text):
		if text:
			self.inputCtrl.SetValue(text)
			common.report(_("Loaded"))
		else:
			common.report(_("Nothing to load"))

	def _onOpChange(self, evt):
		op = self.opCtrl.GetSelection()
		isTranslate = op == self.OP_TRANSLATE
		isDetect = op == self.OP_DETECT
		self.tgtCtrl.Enable(not isDetect)
		self.srcCtrl.Enable(not isDetect)
		self.modeCtrl.Enable(isTranslate)

	def onGo(self, evt):
		text = self.inputCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text"))
			return
		op = self.opCtrl.GetSelection()
		src = self._srcCodes[self.srcCtrl.GetSelection()]
		tgt = self._tgtCodes[self.tgtCtrl.GetSelection()]
		mode = list(constants.TRANSLATE_MODES)[self.modeCtrl.GetSelection()]
		conf = config.conf()
		self.goBtn.Enable(False)

		def work(cancel, progress):
			if op == self.OP_TRANSLATE:
				r = self._cli.translate(
					text, source_language_code=src, target_language_code=tgt,
					model=conf.get("translateModel"), mode=mode, cancel=cancel)
				return r.get("translated_text", "")
			if op == self.OP_TRANSLITERATE:
				r = self._cli.transliterate(
					text, source_language_code=src, target_language_code=tgt, cancel=cancel)
				return r.get("transliterated_text", "")
			r = self._cli.detect_language(text, cancel=cancel)
			code = r.get("language_code") or _("unknown")
			name = constants.LANGUAGES.get(code, code)
			script = r.get("script_code")
			out = _("Detected language: {name} ({code})").format(name=name, code=code)
			if script:
				out += "\n" + _("Script: {script}").format(script=script)
			return out

		def ok(result):
			self.goBtn.Enable(True)
			self.outputCtrl.SetValue(result)
			common.report(_("Done"))

		def bad(exc):
			self.goBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI"), message=_("Processing..."), parent=self)

	def onCopy(self, evt):
		text = self.outputCtrl.GetValue()
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
