# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Translation dialog (translate, transliterate and detect language).

Layout: input text, then a single Operation dropdown that selects Translation,
Transliteration or Language detection - there are no duplicate operation
entries elsewhere. Instead of "from selection" / "from clipboard" the dialog
offers Upload document, which accepts TXT, DOCX, EPUB and PDF/image files (PDFs
and images are read with Sarvam OCR first). Save as TXT / DOCX appears only
after the operation completes.
"""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import textextract
from .. import imaging
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

		# 3) Upload document (replaces selection / clipboard).
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Upload document (text, Word, EPUB, PDF, image)..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		helper.addItem(up)

		# 4) Languages and style.
		langRow = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		srcLabels, self._srcCodes = common.language_choices(include_auto=True)
		self.srcCtrl = langRow.addLabeledControl(_("&Source language:"), wx.Choice, choices=srcLabels)
		common.select_in_combo(self.srcCtrl, self._srcCodes, conf.get("translateSourceLang"))
		tgtLabels, self._tgtCodes = common.language_choices()
		self.tgtCtrl = langRow.addLabeledControl(_("&Target language:"), wx.Choice, choices=tgtLabels)
		common.select_in_combo(self.tgtCtrl, self._tgtCodes, conf.get("translateTargetLang"))
		helper.addItem(langRow.sizer)

		self.modeCtrl = helper.addLabeledControl(
			_("Translation st&yle:"), wx.Choice, choices=list(constants.TRANSLATE_MODES))
		common.select_in_combo(self.modeCtrl, list(constants.TRANSLATE_MODES), conf.get("translateMode"))

		# 5) Run.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.goBtn = go.addButton(self, label=_("&Go"))
		self.goBtn.Bind(wx.EVT_BUTTON, self.onGo)
		helper.addItem(go)

		# 6) Result + save bar (hidden until success).
		self.outputCtrl = helper.addLabeledControl(
			_("&Result:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(600, 180))
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.outputCtrl.GetValue(), "translation")

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

	def _onOpChange(self, evt):
		op = self.opCtrl.GetSelection()
		isDetect = op == self.OP_DETECT
		self.srcCtrl.Enable(not isDetect)
		self.tgtCtrl.Enable(not isDetect)
		self.modeCtrl.Enable(op == self.OP_TRANSLATE)

	# -- upload -------------------------------------------------------------
	def onUpload(self, evt):
		doc_exts = list(textextract.SUPPORTED_EXTENSIONS) + list(constants.OCR_INPUT_EXTENSIONS)
		exts = ";".join("*" + e for e in doc_exts)
		with wx.FileDialog(self, _("Upload a document"),
				wildcard=_("Documents (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		ext = os.path.splitext(path)[1].lower()
		ocr_lang = config.conf().get("ocrLanguage")
		needs_ocr = ext in constants.OCR_INPUT_EXTENSIONS

		def work(cancel, progress):
			if not needs_ocr:
				return textextract.extract_text(path)
			# PDFs and images are read with Sarvam OCR first.
			pdf_path, is_temp = imaging.ensure_pdf(path)
			try:
				res = self._cli.document_ocr(
					pdf_path, language=ocr_lang,
					output_format=config.conf().get("ocrOutputFormat"),
					cancel=cancel, progress=progress)
				return res.get("text", "")
			finally:
				if is_temp:
					try:
						os.remove(pdf_path)
					except OSError:
						pass

		def ok(text):
			self.inputCtrl.ChangeValue(text)
			common.report(_("Document loaded ({n} characters)").format(n=len(text)))
			self.inputCtrl.SetFocus()

		tasks.run_task(work, on_success=ok,
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"),
			message=_("Reading document with OCR...") if needs_ocr else _("Reading document..."),
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
		conf = config.conf()
		self.goBtn.Enable(False)
		self.saveBar.show(False)

		def work(cancel, progress):
			if op == self.OP_TRANSLATE:
				return self._cli.translate_long(
					text, source_language_code=src, target_language_code=tgt,
					model=conf.get("translateModel"), mode=mode,
					cancel=cancel, progress=progress,
					concurrency=common.batch_concurrency())
			if op == self.OP_TRANSLITERATE:
				r = self._cli.transliterate(
					text, source_language_code=src, target_language_code=tgt, cancel=cancel)
				return r.get("transliterated_text", "")
			r = self._cli.detect_language(text, cancel=cancel)
			code = r.get("language_code") or _("unknown")
			name = constants.LANGUAGES.get(code, code)
			out = _("Detected language: {name} ({code})").format(name=name, code=code)
			script = r.get("script_code")
			if script:
				out += "\n" + _("Script: {script}").format(script=script)
			return out

		def ok(result):
			self.goBtn.Enable(True)
			self.outputCtrl.ChangeValue(result)
			self.saveBar.show(True)
			common.report(_("Done. Save options are now available."))
			self.outputCtrl.SetFocus()

		def bad(exc):
			self.goBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI"), message=_("Processing..."), parent=self)
