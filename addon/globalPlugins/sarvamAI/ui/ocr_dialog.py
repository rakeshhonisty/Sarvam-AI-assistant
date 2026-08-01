# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""OCR dialog, powered by Sarvam Document Intelligence.

Sarvam Cloud OCR is the only engine (the former Windows OCR engine was removed
because running two engines caused conflicting results). Sarvam's document
digitization service performs layout analysis, so headings, lists, tables,
multi-column text and reading order are preserved rather than flattened.

Order: choose a PDF or image, choose the document language (Auto detect by
default), press Perform OCR. Only after a successful recognition do the save
options appear: Markdown keeps Sarvam's original structured output, Word
recreates real headings and tables, and plain text is also available.
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
from .. import imaging
from . import common


class OcrDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the OCR dialog.
		super().__init__(parent, title=_("Sarvam AI - OCR (Document Intelligence)"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._path = None
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Choose the document.
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = up.addButton(self, label=_("&Choose PDF or image..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		helper.addItem(up)
		# Translators: shows the selected OCR document.
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Document: none selected")))

		# 2) Language (Auto detect first) and output structure.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._langCodes = [constants.OCR_AUTO_LANGUAGE] + list(constants.OCR_LANGUAGES.keys())
		langLabels = [_("Auto detect")] + [
			"%s (%s)" % (name, code) for code, name in constants.OCR_LANGUAGES.items()]
		self.langCtrl = row.addLabeledControl(_("Document &language:"), wx.Choice, choices=langLabels)
		common.select_in_combo(self.langCtrl, self._langCodes,
			conf.get("ocrLanguage") or constants.OCR_AUTO_LANGUAGE)
		self._formatKeys = list(constants.OCR_OUTPUT_FORMATS)
		self.formatCtrl = row.addLabeledControl(
			_("Output st&ructure:"), wx.Choice,
			choices=[_("Markdown (keeps headings and tables)"), _("HTML"), _("JSON")])
		common.select_in_combo(self.formatCtrl, self._formatKeys,
			conf.get("ocrOutputFormat") or constants.DEFAULT_OCR_OUTPUT_FORMAT)
		helper.addItem(row.sizer)

		# 3) Perform OCR.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.ocrBtn = go.addButton(self, label=_("Perform &OCR"))
		self.ocrBtn.Bind(wx.EVT_BUTTON, self.onPerformOcr)
		helper.addItem(go)

		# 4) Result. Structure is preserved exactly as Sarvam returned it.
		self.textCtrl = helper.addLabeledControl(
			_("Recognised &text:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(640, 280))

		# 5) Save bar with Markdown, hidden until OCR succeeds.
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.textCtrl.GetValue(), "ocr",
			markdown=True, include_md=True)

		# 6) Send the recognised text on to another Sarvam feature.
		more = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.translateBtn = more.addButton(self, label=_("Tr&anslate this text"))
		self.translateBtn.Bind(wx.EVT_BUTTON, self.onTranslate)
		self.aiBtn = more.addButton(self, label=_("Send to AI &Workforce"))
		self.aiBtn.Bind(wx.EVT_BUTTON, self.onSendToAI)
		closeBtn = more.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(more)
		self._showFollowUp(False)

		self._updateOcrButton()
		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _updateOcrButton(self):
		self.ocrBtn.Enable(self._path is not None)

	def _showFollowUp(self, visible):
		for b in (self.translateBtn, self.aiBtn):
			b.Show(visible)
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	def onChooseFile(self, evt):
		exts = ";".join("*" + e for e in constants.OCR_INPUT_EXTENSIONS)
		with wx.FileDialog(self, _("Choose a PDF or image"),
				wildcard=_("PDF and images (%s)|%s|All files (*.*)|*.*") % (exts, exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			self._path = fd.GetPath()
		name = os.path.basename(self._path)
		try:
			mb = os.path.getsize(self._path) / (1024.0 * 1024.0)
			self.sourceLabel.SetLabel(_("Document: {name} ({size:.1f} MB)").format(name=name, size=mb))
		except OSError:
			self.sourceLabel.SetLabel(_("Document: {name}").format(name=name))
		common.report(_("Document selected. Press Perform OCR."))
		self._updateOcrButton()
		self.ocrBtn.SetFocus()

	# -- perform ------------------------------------------------------------
	def onPerformOcr(self, evt):
		if not self._path:
			common.report(_("Choose a PDF or image first"))
			return
		path = self._path
		language = self._langCodes[self.langCtrl.GetSelection()]
		out_format = self._formatKeys[self.formatCtrl.GetSelection()]
		self.ocrBtn.Enable(False)
		self.saveBar.show(False)
		self._showFollowUp(False)

		def work(cancel, progress):
			# Images are wrapped into a one-page PDF; PDFs pass straight through
			# so multi-page documents keep their page order and layout.
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
			self.ocrBtn.Enable(True)
			text = result.get("text", "")
			self.textCtrl.ChangeValue(text)
			self.saveBar.show(True)
			self._showFollowUp(True)
			common.report(_("Recognised {n} characters. Save options are now available.").format(n=len(text)))
			self.textCtrl.SetFocus()

		def bad(exc):
			self.ocrBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - OCR"),
			message=_("Recognising document with Sarvam Document Intelligence..."),
			parent=self)

	# -- follow-up ----------------------------------------------------------
	def onTranslate(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			return
		from .translate import TranslateDialog
		TranslateDialog(self, initial_text=text).Show()

	def onSendToAI(self, evt):
		text = self.textCtrl.GetValue().strip()
		if not text:
			return
		from .workforce import WorkforceDialog
		WorkforceDialog(self, initial_context=text).Show()
