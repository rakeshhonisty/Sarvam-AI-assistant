# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Documents and OCR, powered by Sarvam Document AI (Sarvam Vision 2.1).

Two tasks share one dialog:

* **Read the document** - OCR of PDFs, scans, photos and ZIPs of page images
  in 23 languages, preserving headings, tables, multi-column text and reading
  order. Download as Word, Markdown, HTML, text, Excel/CSV (tables) or JSON.
* **Extract data** (agentic) - describe in plain words what you need ("invoice
  number, date, seller, every line item with quantity and price"). The chat
  model turns that into an extraction schema, Document AI fills it in, and
  the result downloads as Excel, CSV or JSON - ready for a spreadsheet.
"""

import json
import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import agent
from .. import constants
from .. import config
from .. import client
from .. import tasks
from . import common

OP_READ = 0
OP_EXTRACT = 1


class OcrDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the documents / OCR dialog.
		super().__init__(parent, title=_("Sarvam AI - Documents and OCR"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._path = None
		self._extractFile = None
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Choose the document.
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = up.addButton(self, label=_("&Choose PDF, image or ZIP..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		helper.addItem(up)
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Document: none selected")))

		# 2) Task.
		self.opCtrl = helper.addLabeledControl(
			_("&Task:"), wx.Choice,
			choices=[_("Read the document (OCR, keeps headings and tables)"),
				_("Extract data into a spreadsheet (describe what you need)")])
		self.opCtrl.SetSelection(OP_READ)
		self.opCtrl.Bind(wx.EVT_CHOICE, self._onOp)

		# 3) Language and output structure.
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

		# 4) Extraction options.
		self.fieldsCtrl = helper.addLabeledControl(
			# Translators: plain-language description of the data to extract.
			_("&Describe the data to extract (for example: invoice number, date, seller, "
				"and each line item with quantity and price):"),
			wx.TextCtrl, style=wx.TE_MULTILINE, size=(600, 70))
		exRow = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._exFormats = list(constants.EXTRACT_OUTPUT_FORMATS)
		self.exFormatCtrl = exRow.addLabeledControl(
			_("Spreadsheet f&ormat:"), wx.Choice,
			choices=[_("Excel (.xlsx)"), _("CSV (.csv)"), _("JSON (.json)")])
		common.select_in_combo(self.exFormatCtrl, self._exFormats, conf.get("extractFormat") or "xlsx")
		self._exModes = list(constants.EXTRACT_MODES)
		self.exModeCtrl = exRow.addLabeledControl(
			_("Accurac&y:"), wx.Choice,
			choices=[_("Basic (faster)"), _("Advanced (best for complex documents)")])
		common.select_in_combo(self.exModeCtrl, self._exModes, conf.get("extractMode") or "basic")
		helper.addItem(exRow.sizer)
		self._extractControls = [self.fieldsCtrl, self.exFormatCtrl, self.exModeCtrl]

		# 5) Run.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.runBtn = go.addButton(self, label=_("&Run"))
		self.runBtn.Bind(wx.EVT_BUTTON, self.onRun)
		self.saveExtractBtn = go.addButton(self, label=_("Download the &spreadsheet..."))
		self.saveExtractBtn.Bind(wx.EVT_BUTTON, self.onSaveExtract)
		self.saveExtractBtn.Show(False)
		helper.addItem(go)

		# 6) Result.
		self.textCtrl = helper.addLabeledControl(
			_("Result &text:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_RICH2, size=(640, 260))
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.textCtrl.GetValue(), "document",
			markdown=True, include_md=True, title=_("Document"))

		# 7) Send the text on to another Sarvam feature.
		more = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.translateBtn = more.addButton(self, label=_("Tr&anslate this text"))
		self.translateBtn.Bind(wx.EVT_BUTTON, self.onTranslate)
		self.ttsBtn = more.addButton(self, label=_("Read &aloud with Sarvam"))
		self.ttsBtn.Bind(wx.EVT_BUTTON, self.onSpeak)
		self.aiBtn = more.addButton(self, label=_("Send to AI &Workforce"))
		self.aiBtn.Bind(wx.EVT_BUTTON, self.onSendToAI)
		closeBtn = more.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(more)
		self._showFollowUp(False)

		self._updateRun()
		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self._onOp(None)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _op(self):
		return self.opCtrl.GetSelection()

	def _onOp(self, evt):
		extract = self._op() == OP_EXTRACT
		for c in self._extractControls:
			c.Show(extract)
			try:
				c.GetPrevSibling().Show(extract)
			except Exception:
				pass
		self.formatCtrl.Enable(not extract)
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	def _updateRun(self):
		self.runBtn.Enable(self._path is not None)

	def _showFollowUp(self, visible):
		for b in (self.translateBtn, self.ttsBtn, self.aiBtn):
			b.Show(visible)
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	def onChooseFile(self, evt):
		exts = ";".join("*" + e for e in constants.OCR_INPUT_EXTENSIONS)
		with wx.FileDialog(self, _("Choose a PDF, image or ZIP of page images"),
				wildcard=_("PDF, images and ZIP (%s)|%s|All files (*.*)|*.*") % (exts, exts),
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
		common.report(_("Document selected. Choose the task and press Run."))
		self._updateRun()
		self.opCtrl.SetFocus()

	# -- run ----------------------------------------------------------------
	def onRun(self, evt):
		if not self._path:
			common.report(_("Choose a document first"))
			return
		if self._op() == OP_EXTRACT:
			self._runExtract()
		else:
			self._runRead()

	def _runRead(self):
		path = self._path
		language = self._langCodes[self.langCtrl.GetSelection()]
		out_format = self._formatKeys[self.formatCtrl.GetSelection()]
		self.runBtn.Enable(False)
		self.saveBar.show(False)
		self._showFollowUp(False)

		def ok(result):
			self.runBtn.Enable(True)
			text = result.get("text", "")
			self.textCtrl.ChangeValue(text)
			self.saveBar.show(True)
			self._showFollowUp(True)
			pages = result.get("pages")
			msg = _("Recognised {n} characters.").format(n=len(text))
			if pages:
				msg += " " + _("{p} pages.").format(p=pages)
			common.report(msg + " " + _("Download options are now available."))
			self.textCtrl.SetFocus()

		def bad(exc):
			self.runBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(
			lambda cancel, progress: self._cli.document_ocr(
				path, language=language, output_format=out_format, cancel=cancel, progress=progress),
			on_success=ok, on_error=bad, title=_("Sarvam AI - Documents"),
			message=_("Reading the document with Sarvam Document AI..."), parent=self)

	def _runExtract(self):
		description = self.fieldsCtrl.GetValue().strip()
		if not description:
			common.report(_("Describe the data you want to extract first"))
			self.fieldsCtrl.SetFocus()
			return
		path = self._path
		language = self._langCodes[self.langCtrl.GetSelection()]
		fmt = self._exFormats[self.exFormatCtrl.GetSelection()]
		mode = self._exModes[self.exModeCtrl.GetSelection()]
		conf = config.conf()
		conf["extractFormat"] = fmt
		conf["extractMode"] = mode
		self.runBtn.Enable(False)
		self.saveBar.show(False)
		self.saveExtractBtn.Show(False)

		def work(cancel, progress):
			schema = agent.build_extract_schema(
				self._cli, description, model=conf.get("chatModel"), cancel=cancel)
			res = self._cli.docai_extract(path, schema, output_format=fmt, mode=mode,
				language=language, cancel=cancel, progress=progress)
			res["schema"] = schema
			return res

		def ok(res):
			self.runBtn.Enable(True)
			self._extractFile = (res.get("file_bytes"), fmt)
			data = res.get("data")
			text = agent.extract_result_to_markdown(data) if data else ""
			if not text and res.get("file_bytes") and fmt == "csv":
				text = res["file_bytes"].decode("utf-8-sig", "replace")
			if not text:
				text = _("Extraction finished. Use Download the spreadsheet to save it.")
			if fmt == "json" and data is not None:
				self._extractFile = (json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "json")
			self.textCtrl.ChangeValue(text)
			self.saveBar.show(True)
			self.saveExtractBtn.Show(bool(self._extractFile[0]))
			self._showFollowUp(True)
			self.Layout()
			common.report(_("Data extracted. Download the spreadsheet or read it in the result box."))
			(self.saveExtractBtn if self._extractFile[0] else self.textCtrl).SetFocus()

		def bad(exc):
			self.runBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad, title=_("Sarvam AI - Extract data"),
			message=_("Planning the fields, then extracting them with Document AI..."), parent=self)

	def onSaveExtract(self, evt):
		if not self._extractFile or not self._extractFile[0]:
			return
		data, fmt = self._extractFile
		base = os.path.splitext(os.path.basename(self._path or "data"))[0] + "-data." + fmt
		path = common.ask_save_path(self, base, "*.%s|*.%s" % (fmt, fmt))
		if not path:
			return
		try:
			with open(path, "wb") as f:
				f.write(data)
			common.report(_("Saved {name}").format(name=os.path.basename(path)))
		except OSError as e:
			common.error_dialog(self, e)

	# -- follow-up ----------------------------------------------------------
	def onTranslate(self, evt):
		text = self.textCtrl.GetValue().strip()
		if text:
			from .translate import TranslateDialog
			TranslateDialog(self, initial_text=text).Show()

	def onSpeak(self, evt):
		text = self.textCtrl.GetValue().strip()
		if text:
			from .tts import TextToSpeechDialog
			TextToSpeechDialog(self, initial_text=text).Show()

	def onSendToAI(self, evt):
		text = self.textCtrl.GetValue().strip()
		if text:
			from .workforce import WorkforceDialog
			name = os.path.basename(self._path) if self._path else None
			WorkforceDialog(self, initial_context=text, context_name=name).Show()
