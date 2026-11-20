# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Translation dialog (translate, transliterate, detect language) and whole
document translation.

Text: type, paste or upload almost any file (documents, PDFs, scans and audio
are read automatically), pick the Operation and languages, press Go, then
Download the result in the format you need.

Whole documents: "Translate a document file and keep its format" sends a PDF,
Word, Excel, PowerPoint, HTML, Markdown or text file to Sarvam document
translation. The translated copy comes back in the same format with its
layout, tables and styles kept, and is saved next to your other downloads.
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
from .. import fileio
from .. import models
from .. import tasks
from . import common


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

		# 1) Input text.
		self.inputCtrl = helper.addLabeledControl(
			_("&Input text:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 160))
		self.inputCtrl.SetValue(initial_text or "")

		# 2) Operation - the only place operations are chosen.
		self.opCtrl = helper.addLabeledControl(
			_("&Operation:"), wx.Choice,
			choices=[_("Translation"), _("Transliteration"), _("Language detection")])
		self.opCtrl.SetSelection(operation if operation in (0, 1, 2) else 0)
		self.opCtrl.Bind(wx.EVT_CHOICE, self._onOpChange)

		# 3) Upload (text extraction) and whole-document translation.
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Upload file to read its text..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		# Translators: translates a whole file and saves it in the same format.
		self.docBtn = up.addButton(self, label=_("Translate a document &file and keep its format..."))
		self.docBtn.Bind(wx.EVT_BUTTON, self.onTranslateDocument)
		helper.addItem(up)

		# 4) Model, languages and style.
		self._modelIds = list(models.translate_ids())
		self.modelCtrl = helper.addLabeledControl(
			_("Translation &model:"), wx.Choice,
			choices=[models.label_of("translate", m) for m in self._modelIds])
		common.select_in_combo(self.modelCtrl, self._modelIds,
			conf.get("translateModel") or models.DEFAULT_TRANSLATE_MODEL)
		self.modelCtrl.Bind(wx.EVT_CHOICE, self._onModel)
		langRow = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.srcCtrl = langRow.addLabeledControl(_("&Source language:"), wx.Choice, choices=[])
		self.tgtCtrl = langRow.addLabeledControl(_("&Target language:"), wx.Choice, choices=[])
		helper.addItem(langRow.sizer)
		self._srcCodes, self._tgtCodes = [], []
		self._fillLanguages(conf.get("translateSourceLang"), conf.get("translateTargetLang"))

		self.modeCtrl = helper.addLabeledControl(
			_("Translation st&yle (Mayura):"), wx.Choice, choices=list(constants.TRANSLATE_MODES))
		common.select_in_combo(self.modeCtrl, list(constants.TRANSLATE_MODES), conf.get("translateMode"))

		# 5) Run.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.goBtn = go.addButton(self, label=_("&Go"))
		self.goBtn.Bind(wx.EVT_BUTTON, self.onGo)
		helper.addItem(go)

		# 6) Result + download bar (hidden until success).
		self.outputCtrl = helper.addLabeledControl(
			_("&Result:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 180))
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.outputCtrl.GetValue(), "translation", markdown=True,
			title=_("Translation"))

		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		self._onOpChange(None)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.inputCtrl.SetFocus()

	def _model(self):
		return self._modelIds[max(0, self.modelCtrl.GetSelection())]

	def _fillLanguages(self, src=None, tgt=None):
		extended = self._model().startswith("sarvam-translate")
		prev_src = src or (self._srcCodes[self.srcCtrl.GetSelection()] if self._srcCodes else None)
		prev_tgt = tgt or (self._tgtCodes[self.tgtCtrl.GetSelection()] if self._tgtCodes else None)
		srcLabels, self._srcCodes = common.language_choices(include_auto=True, extended=extended)
		tgtLabels, self._tgtCodes = common.language_choices(extended=extended)
		self.srcCtrl.Set(srcLabels)
		self.tgtCtrl.Set(tgtLabels)
		common.select_in_combo(self.srcCtrl, self._srcCodes, prev_src)
		common.select_in_combo(self.tgtCtrl, self._tgtCodes, prev_tgt or "en-IN")

	def _onModel(self, evt):
		self._fillLanguages()
		self._onOpChange(None)
		common.report(_("{n} target languages").format(n=len(self._tgtCodes)))

	def _onOpChange(self, evt):
		op = self.opCtrl.GetSelection()
		isDetect = op == self.OP_DETECT
		self.srcCtrl.Enable(not isDetect)
		self.tgtCtrl.Enable(not isDetect)
		self.modelCtrl.Enable(op == self.OP_TRANSLATE)
		self.modeCtrl.Enable(op == self.OP_TRANSLATE and self._model().startswith("mayura"))

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
			self.inputCtrl.ChangeValue(text)
			common.report(_("File loaded ({n} characters)").format(n=len(text)))
			self.inputCtrl.SetFocus()

		tasks.run_task(lambda cancel, progress: fileio.read_any(path, self._cli, conf, cancel, progress),
			on_success=ok, on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"), message=_("Reading {name}...").format(name=os.path.basename(path)),
			parent=self)

	# -- whole document -----------------------------------------------------
	def onTranslateDocument(self, evt):
		exts = list(constants.DOCTR_EXTENSIONS)
		with wx.FileDialog(self, _("Choose a document to translate"),
				wildcard=fileio.wildcard(_("PDF, Word, Excel, PowerPoint, HTML, Markdown, text"), exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		src = self._srcCodes[self.srcCtrl.GetSelection()]
		tgt = self._tgtCodes[self.tgtCtrl.GetSelection()]
		if src == constants.AUTO_DETECT:
			gui.messageBox(_(
				"Document translation needs the document's language. Choose it in "
				"Source language, then try again."),
				_("Sarvam AI"), wx.OK | wx.ICON_INFORMATION, self)
			self.srcCtrl.SetFocus()
			return
		with wx.DirDialog(self, _("Choose where to save the translated document"),
				defaultPath=common.default_download_folder()) as dd:
			if dd.ShowModal() != wx.ID_OK:
				return
			out_dir = dd.GetPath()
		self.docBtn.Enable(False)

		def ok(paths):
			self.docBtn.Enable(True)
			names = ", ".join(os.path.basename(p) for p in paths)
			gui.messageBox(
				_("Translated document saved, in the same format as the original:\n{names}\n\nFolder: {folder}").format(
					names=names, folder=out_dir),
				_("Sarvam AI - Document translation"), wx.OK | wx.ICON_INFORMATION, self)

		def bad(exc):
			self.docBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(
			lambda cancel, progress: self._cli.translate_document(
				path, src, [tgt], out_dir, cancel=cancel, progress=progress),
			on_success=ok, on_error=bad, title=_("Sarvam AI - Document translation"),
			message=_("Translating {name} to {lang}. Large documents can take several minutes...").format(
				name=os.path.basename(path), lang=constants.language_name(tgt)),
			parent=self)

	# -- run ----------------------------------------------------------------
	def onGo(self, evt):
		text = self.inputCtrl.GetValue().strip()
		if not text:
			common.report(_("There is no text"))
			return
		op = self.opCtrl.GetSelection()
		src = self._srcCodes[self.srcCtrl.GetSelection()]
		tgt = self._tgtCodes[self.tgtCtrl.GetSelection()]
		mode = list(constants.TRANSLATE_MODES)[self.modeCtrl.GetSelection()]
		model = self._model()
		conf = config.conf()
		conf["translateModel"] = model
		conf["translateSourceLang"] = src
		conf["translateTargetLang"] = tgt
		self.goBtn.Enable(False)
		self.saveBar.show(False)

		def work(cancel, progress):
			if op == self.OP_TRANSLATE:
				return self._cli.translate_long(
					text, source_language_code=src, target_language_code=tgt,
					model=model, mode=mode, cancel=cancel, progress=progress,
					concurrency=common.batch_concurrency())
			if op == self.OP_TRANSLITERATE:
				r = self._cli.transliterate(
					text, source_language_code=src, target_language_code=tgt, cancel=cancel)
				return r.get("transliterated_text", "")
			r = self._cli.detect_language(text, cancel=cancel)
			code = r.get("language_code") or _("unknown")
			out = _("Detected language: {name} ({code})").format(
				name=constants.language_name(code), code=code)
			script = r.get("script_code")
			if script:
				out += "\n" + _("Script: {script}").format(script=script)
			return out

		def ok(result):
			self.goBtn.Enable(True)
			self.outputCtrl.ChangeValue(result)
			self.saveBar.show(True)
			common.report(_("Done. Download options are now available."))
			self.outputCtrl.SetFocus()

		def bad(exc):
			self.goBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI"), message=_("Processing..."), parent=self)
