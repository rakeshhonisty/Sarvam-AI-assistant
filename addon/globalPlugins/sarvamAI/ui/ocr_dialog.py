# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""OCR dialog.

Primary engine: **Sarvam Document OCR** (the Sarvam document-digitization
service), which recognises 23 languages from a PDF or image and returns
structured text. A secondary **Windows OCR** engine is offered for instant,
offline recognition. Recognised text can be translated or summarised with
Sarvam."""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import ocr
from .. import imaging
from .. import docwriter
from . import common
from .translate import TranslateDialog
from .chat import ChatDialog


class OcrDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the OCR dialog.
		super().__init__(parent, title=_("Sarvam AI - OCR"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Engine + language row.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		# Translators: choose the OCR engine.
		self.engineCtrl = row.addLabeledControl(
			_("OCR &engine:"), wx.Choice,
			choices=[_("Sarvam Document OCR (online, 23 languages)"),
				_("Windows OCR (offline, instant)")])
		self.engineCtrl.SetSelection(
			0 if conf.get("ocrEngine") == constants.OCR_ENGINE_SARVAM else 1)
		self.engineCtrl.Bind(wx.EVT_CHOICE, self._onEngineChange)

		self._ocrLangCodes = list(constants.OCR_LANGUAGES.keys())
		langLabels = ["%s (%s)" % (name, code) for code, name in constants.OCR_LANGUAGES.items()]
		# Translators: document language for Sarvam OCR.
		self.langCtrl = row.addLabeledControl(_("Document &language:"), wx.Choice, choices=langLabels)
		common.select_in_combo(self.langCtrl, self._ocrLangCodes, conf.get("ocrLanguage"))
		helper.addItem(row.sizer)

		# Source buttons.
		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = srcBtns.addButton(self, label=_("Recognise document / image &file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onFile)
		self.clipBtn = srcBtns.addButton(self, label=_("Recognise clip&board image"))
		self.clipBtn.Bind(wx.EVT_BUTTON, self.onClipboard)
		self.screenBtn = srcBtns.addButton(self, label=_("Recognise current &screen / object"))
		self.screenBtn.Bind(wx.EVT_BUTTON, self.onScreen)
		helper.addItem(srcBtns)

		# Recognised text is editable so the user can correct it before saving,
		# copying, translating or summarising.
		self.textCtrl = helper.addLabeledControl(
			_("Recognised &text (editable):"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(620, 280))

		# Row 1: clipboard / edit actions.
		editBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.copyBtn = editBtns.addButton(self, label=_("&Copy text"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.clearBtn = editBtns.addButton(self, label=_("C&lear"))
		self.clearBtn.Bind(wx.EVT_BUTTON, self.onClear)
		helper.addItem(editBtns)

		# Row 2: save / export actions.
		saveBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.saveTxtBtn = saveBtns.addButton(self, label=_("Save as &text (.txt)"))
		self.saveTxtBtn.Bind(wx.EVT_BUTTON, self.onSaveTxt)
		self.saveDocBtn = saveBtns.addButton(self, label=_("Save as &Word (.docx)"))
		self.saveDocBtn.Bind(wx.EVT_BUTTON, self.onSaveDocx)
		helper.addItem(saveBtns)

		# Row 3: Sarvam post-processing and close.
		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.translateBtn = btns.addButton(self, label=_("Tr&anslate with Sarvam"))
		self.translateBtn.Bind(wx.EVT_BUTTON, self.onTranslate)
		self.summariseBtn = btns.addButton(self, label=_("Su&mmarise with Sarvam"))
		self.summariseBtn.Bind(wx.EVT_BUTTON, self.onSummarise)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self._onEngineChange(None)
		self.fileBtn.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _sarvamSelected(self):
		return self.engineCtrl.GetSelection() == 0

	def _onEngineChange(self, evt):
		sarvam = self._sarvamSelected()
		self.langCtrl.Enable(sarvam)
		if not sarvam and not ocr.is_available():
			common.report(_("Windows OCR is not available on this system"))

	def _ocrLanguage(self):
		return self._ocrLangCodes[self.langCtrl.GetSelection()]

	def _setText(self, text):
		self.textCtrl.SetValue(text)
		common.report(_("Text recognised"))
		self.textCtrl.SetFocus()

	def _sarvamOcrPath(self, path):
		"""Run Sarvam document OCR on a PDF/image path in the background."""
		language = self._ocrLanguage()
		out_format = config.conf().get("ocrOutputFormat")

		def work(cancel, progress):
			pdf_path, is_temp = imaging.ensure_pdf(path)
			try:
				return self._cli.document_ocr(
					pdf_path, language=language, output_format=out_format,
					cancel=cancel, progress=progress)
			finally:
				if is_temp:
					try:
						os.remove(pdf_path)
					except OSError:
						pass

		def ok(result):
			self._setText(result.get("text", ""))

		def bad(exc):
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - OCR"),
			message=_("Recognising document with Sarvam..."), parent=self)

	# -- sources ------------------------------------------------------------
	def onFile(self, evt):
		if self._sarvamSelected():
			exts = ";".join("*" + e for e in constants.OCR_INPUT_EXTENSIONS)
			prompt = _("Open PDF or image")
		else:
			exts = ";".join("*" + e for e in constants.IMAGE_EXTENSIONS)
			prompt = _("Open image")
		with wx.FileDialog(
				self, prompt,
				wildcard=_("Supported files (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		if self._sarvamSelected():
			self._sarvamOcrPath(path)
		else:
			self._windowsOcrImage(path)

	def onClipboard(self, evt):
		path = ocr.save_clipboard_image_to_temp()
		if not path:
			common.report(_("The clipboard has no image"))
			return
		if self._sarvamSelected():
			self._sarvamOcrPath(path)
		else:
			self._windowsOcrImage(path)

	def onScreen(self, evt):
		if self._sarvamSelected():
			try:
				path = ocr.capture_navigator_png()
			except Exception as e:
				common.error_dialog(self, e)
				return
			self._sarvamOcrPath(path)
		else:
			common.report(_("Recognising screen"))
			ocr.recognize_screen(self._setText, lambda e: common.error_dialog(self, e))

	def _windowsOcrImage(self, path):
		if not ocr.is_available():
			common.report(_("Windows OCR is not available"))
			return
		common.report(_("Recognising image"))
		ocr.recognize_image_file(path, self._setText, lambda e: common.error_dialog(self, e))

	# -- actions ------------------------------------------------------------
	def onCopy(self, evt):
		text = self.textCtrl.GetValue()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			common.report(_("Copied"))

	def onClear(self, evt):
		self.textCtrl.SetValue("")
		common.report(_("Cleared"))
		self.textCtrl.SetFocus()

	def onSaveTxt(self, evt):
		self._save(_("Save as text"), "ocr.txt",
			_("Text files (*.txt)|*.txt"), docwriter.write_txt)

	def onSaveDocx(self, evt):
		self._save(_("Save as Word document"), "ocr.docx",
			_("Word documents (*.docx)|*.docx"), docwriter.write_docx)

	def _save(self, title, default_name, wildcard, writer):
		text = self.textCtrl.GetValue()
		if not text.strip():
			common.report(_("Nothing to save"))
			return
		with wx.FileDialog(
				self, title, defaultDir=common.default_output_folder(),
				defaultFile=default_name, wildcard=wildcard,
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			writer(text, path)
			common.report(_("Saved"))
		except Exception as e:
			common.error_dialog(self, e)

	def onTranslate(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("Nothing to translate"))
			return
		TranslateDialog(self, initial_text=text).Show()

	def onSummarise(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			common.report(_("Nothing to summarise"))
			return
		ChatDialog(self, initial_text=text, mode="summarize").Show()
