# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""OCR dialog.

Primary engine: Sarvam Document OCR (document-digitization, 23 languages, PDF or
image). Secondary: offline Windows OCR. Choose a source (file / clipboard image
/ screen), then press "Perform OCR". The recognised text is editable and can be
copied, saved as .txt or .docx, or translated / summarised with Sarvam."""

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
		self._source = None  # ("file", path) | ("clipboard", None) | ("screen", None)
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Engine + language.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.engineCtrl = row.addLabeledControl(
			_("OCR &engine:"), wx.Choice,
			choices=[_("Sarvam Document OCR (online, 23 languages)"),
				_("Windows OCR (offline, instant)")])
		self.engineCtrl.SetSelection(
			0 if conf.get("ocrEngine") == constants.OCR_ENGINE_SARVAM else 1)
		self._ocrLangCodes = list(constants.OCR_LANGUAGES.keys())
		langLabels = ["%s (%s)" % (name, code) for code, name in constants.OCR_LANGUAGES.items()]
		self.langCtrl = row.addLabeledControl(_("Document &language:"), wx.Choice, choices=langLabels)
		common.select_in_combo(self.langCtrl, self._ocrLangCodes, conf.get("ocrLanguage"))
		self.engineCtrl.Bind(wx.EVT_CHOICE, lambda e: self.langCtrl.Enable(self._sarvam()))
		helper.addItem(row.sizer)

		# Source selection.
		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = srcBtns.addButton(self, label=_("Choose PDF / image &file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		self.clipBtn = srcBtns.addButton(self, label=_("Use clip&board image"))
		self.clipBtn.Bind(wx.EVT_BUTTON, self.onUseClipboard)
		self.screenBtn = srcBtns.addButton(self, label=_("Use current &screen / object"))
		self.screenBtn.Bind(wx.EVT_BUTTON, self.onUseScreen)
		helper.addItem(srcBtns)

		# Translators: shows the currently selected OCR source.
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Source: none selected")))

		# The OCR trigger.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.ocrBtn = go.addButton(self, label=_("Perform &OCR"))
		self.ocrBtn.Bind(wx.EVT_BUTTON, self.onPerformOcr)
		helper.addItem(go)

		self.textCtrl = helper.addLabeledControl(
			_("Recognised &text (editable):"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(620, 260))

		# Row 1: clipboard + save actions.
		saveBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.copyBtn = saveBtns.addButton(self, label=_("&Copy text"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.saveTxtBtn = saveBtns.addButton(self, label=_("Save as &text (.txt)"))
		self.saveTxtBtn.Bind(wx.EVT_BUTTON, self.onSaveTxt)
		self.saveDocBtn = saveBtns.addButton(self, label=_("Save as &Word (.docx)"))
		self.saveDocBtn.Bind(wx.EVT_BUTTON, self.onSaveDocx)
		helper.addItem(saveBtns)

		# Row 2: Sarvam post-processing + close.
		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.translateBtn = btns.addButton(self, label=_("Tr&anslate with Sarvam"))
		self.translateBtn.Bind(wx.EVT_BUTTON, self.onTranslate)
		self.summariseBtn = btns.addButton(self, label=_("Su&mmarise with Sarvam"))
		self.summariseBtn.Bind(wx.EVT_BUTTON, self.onSummarise)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.langCtrl.Enable(self._sarvam())
		self._updateOcrButton()
		self.SetEscapeId(wx.ID_CLOSE)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	def _sarvam(self):
		return self.engineCtrl.GetSelection() == 0

	def _updateOcrButton(self):
		self.ocrBtn.Enable(self._source is not None)

	def _setSource(self, source, label):
		self._source = source
		self.sourceLabel.SetLabel(_("Source: {what}").format(what=label))
		self._updateOcrButton()
		common.report(_("Source selected. Press Perform OCR."))

	# -- source selection ---------------------------------------------------
	def onChooseFile(self, evt):
		if self._sarvam():
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
		self._setSource(("file", path), os.path.basename(path))

	def onUseClipboard(self, evt):
		self._setSource(("clipboard", None), _("clipboard image"))

	def onUseScreen(self, evt):
		self._setSource(("screen", None), _("current screen / object"))

	# -- perform ------------------------------------------------------------
	def onPerformOcr(self, evt):
		if not self._source:
			common.report(_("Choose a source first"))
			return
		kind, path = self._source
		if kind == "clipboard":
			path = ocr.save_clipboard_image_to_temp()
			if not path:
				common.report(_("The clipboard has no image"))
				return
			kind = "file"
		if self._sarvam():
			self._sarvamOcr(kind, path)
		else:
			self._windowsOcr(kind, path)

	def _sarvamOcr(self, kind, path):
		language = self._ocrLangCodes[self.langCtrl.GetSelection()]
		out_format = config.conf().get("ocrOutputFormat")
		# Screen capture uses wx and must run on the GUI thread, so do it now.
		screen_temp = None
		if kind == "screen":
			try:
				path = ocr.capture_navigator_png()
				screen_temp = path
			except Exception as e:
				common.error_dialog(self, e)
				return

		def work(cancel, progress, src=path, screen_temp=screen_temp):
			pdf_path, is_temp = imaging.ensure_pdf(src)
			try:
				return self._cli.document_ocr(
					pdf_path, language=language, output_format=out_format,
					cancel=cancel, progress=progress)
			finally:
				for p in ((pdf_path if is_temp else None), screen_temp):
					if p:
						try:
							os.remove(p)
						except OSError:
							pass

		tasks.run_task(work, on_success=lambda r: self._setText(r.get("text", "")),
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI - OCR"),
			message=_("Recognising document with Sarvam..."), parent=self)

	def _windowsOcr(self, kind, path):
		if not ocr.is_available():
			common.report(_("Windows OCR is not available"))
			return
		common.report(_("Recognising"))
		if kind == "screen":
			ocr.recognize_screen(self._setText, lambda e: common.error_dialog(self, e))
		else:
			ocr.recognize_image_file(path, self._setText, lambda e: common.error_dialog(self, e))

	def _setText(self, text):
		self.textCtrl.SetValue(text)
		common.report(_("Text recognised"))
		self.textCtrl.SetFocus()

	# -- output -------------------------------------------------------------
	def onCopy(self, evt):
		text = self.textCtrl.GetValue()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			common.report(_("Copied"))
		else:
			common.report(_("Nothing to copy"))

	def onSaveTxt(self, evt):
		self._save("ocr.txt", _("Text files (*.txt)|*.txt"), docwriter.write_txt)

	def onSaveDocx(self, evt):
		self._save("ocr.docx", _("Word documents (*.docx)|*.docx"), docwriter.write_docx)

	def _save(self, default_name, wildcard, writer):
		text = self.textCtrl.GetValue()
		if not text.strip():
			common.report(_("Nothing to save"))
			return
		with wx.FileDialog(
				self, _("Save recognised text"),
				defaultDir=common.default_output_folder(), defaultFile=default_name,
				wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
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
