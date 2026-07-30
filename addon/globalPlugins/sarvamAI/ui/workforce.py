# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""AI Workforce dialog.

A reasoning / agentic layer powered by Sarvam's 105B model (sarvam-105b, 128K
context). The user picks a "worker" role, a reasoning effort (low / medium /
high) and, optionally, wiki grounding, then gives a task. The model reasons
through it in the chosen role and returns the result, which can be edited,
copied or saved as text or a Word document."""

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import docwriter
from . import common
from .tts import _get_selection, _get_clipboard_text


class WorkforceDialog(wx.Dialog):

	def __init__(self, parent, initial_text=""):
		# Translators: title of the AI Workforce dialog.
		super().__init__(parent, title=_("Sarvam AI - AI Workforce (105B)"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Worker role / reasoning effort / grounding.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._roleKeys = [r[0] for r in constants.WORKFORCE_ROLES]
		self.roleCtrl = row.addLabeledControl(
			_("&Worker (role):"), wx.Choice,
			choices=[_(r[1]) for r in constants.WORKFORCE_ROLES])
		common.select_in_combo(self.roleCtrl, self._roleKeys, conf.get("workforceRole"))
		self._effortKeys = list(constants.REASONING_EFFORTS)
		self.effortCtrl = row.addLabeledControl(
			_("&Reasoning effort:"), wx.Choice, choices=self._effortKeys)
		common.select_in_combo(self.effortCtrl, self._effortKeys, conf.get("reasoningEffort"))
		# Translators: checkbox to ground answers in reference/wiki data.
		self.wikiCtrl = row.addItem(wx.CheckBox(self, label=_("Wiki &grounding")))
		self.wikiCtrl.SetValue(bool(conf.get("wikiGrounding")))
		helper.addItem(row.sizer)

		# Task input.
		self.taskCtrl = helper.addLabeledControl(
			_("&Task or question:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(620, 140))
		self.taskCtrl.SetValue(initial_text or "")

		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		b1 = srcBtns.addButton(self, label=_("From se&lection"))
		b1.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_selection()))
		b2 = srcBtns.addButton(self, label=_("From cli&pboard"))
		b2.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_clipboard_text()))
		b3 = srcBtns.addButton(self, label=_("Open te&xt file..."))
		b3.Bind(wx.EVT_BUTTON, self._fromFile)
		helper.addItem(srcBtns)

		# Run.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.runBtn = go.addButton(self, label=_("&Run task"))
		self.runBtn.Bind(wx.EVT_BUTTON, self.onRun)
		helper.addItem(go)

		# Result.
		self.outputCtrl = helper.addLabeledControl(
			_("R&esult:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(620, 260))

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.copyBtn = btns.addButton(self, label=_("&Copy"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.saveTxtBtn = btns.addButton(self, label=_("Save as &text (.txt)"))
		self.saveTxtBtn.Bind(wx.EVT_BUTTON, self.onSaveTxt)
		self.saveDocBtn = btns.addButton(self, label=_("Save as &Word (.docx)"))
		self.saveDocBtn.Bind(wx.EVT_BUTTON, self.onSaveDocx)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.taskCtrl.SetFocus()

	def _load(self, text):
		if text:
			self.taskCtrl.SetValue(text)
			common.report(_("Loaded"))
		else:
			common.report(_("Nothing to load"))

	def _fromFile(self, evt):
		with wx.FileDialog(
				self, _("Open text file"),
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "r", encoding="utf-8", errors="replace") as f:
				self.taskCtrl.SetValue(f.read())
		except Exception as e:
			common.error_dialog(self, e)

	def onRun(self, evt):
		task = self.taskCtrl.GetValue().strip()
		if not task:
			common.report(_("Enter a task first"))
			return
		role_key = self._roleKeys[self.roleCtrl.GetSelection()]
		system_prompt = next(
			(r[2] for r in constants.WORKFORCE_ROLES if r[0] == role_key),
			constants.WORKFORCE_ROLES[0][2])
		effort = self._effortKeys[self.effortCtrl.GetSelection()]
		wiki = self.wikiCtrl.GetValue()
		max_tokens = config.conf().get("workforceMaxTokens")
		messages = [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": task},
		]
		self.runBtn.Enable(False)

		def work(cancel, progress):
			return self._cli.chat(
				messages, model=constants.WORKFORCE_MODEL,
				reasoning_effort=effort, wiki_grounding=wiki,
				max_tokens=max_tokens, cancel=cancel)

		def ok(reply):
			self.runBtn.Enable(True)
			self.outputCtrl.SetValue(reply)
			common.report(_("Done"))
			self.outputCtrl.SetFocus()

		def bad(exc):
			self.runBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - AI Workforce"),
			message=_("The 105B model is reasoning through your task..."), parent=self)

	def onCopy(self, evt):
		text = self.outputCtrl.GetValue()
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
		self._save("workforce.txt", _("Text files (*.txt)|*.txt"), docwriter.write_txt)

	def onSaveDocx(self, evt):
		self._save("workforce.docx", _("Word documents (*.docx)|*.docx"), docwriter.write_docx)

	def _save(self, default_name, wildcard, writer):
		text = self.outputCtrl.GetValue()
		if not text.strip():
			common.report(_("Nothing to save"))
			return
		with wx.FileDialog(
				self, _("Save result"), defaultDir=common.default_output_folder(),
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
