# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Log viewer dialog with refresh, clear and export."""

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import logger
from . import common


class LogViewerDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the log viewer.
		super().__init__(parent, title=_("Sarvam AI - Logs"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.textCtrl = helper.addLabeledControl(
			_("&Log:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(640, 360))
		self._reload()

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		r = btns.addButton(self, label=_("&Refresh"))
		r.Bind(wx.EVT_BUTTON, lambda e: self._reload())
		e = btns.addButton(self, label=_("&Export..."))
		e.Bind(wx.EVT_BUTTON, self.onExport)
		c = btns.addButton(self, label=_("C&lear log"))
		c.Bind(wx.EVT_BUTTON, self.onClear)
		close = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		close.Bind(wx.EVT_BUTTON, lambda ev: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()

	def _reload(self):
		content = logger.readLog()
		self.textCtrl.SetValue(content or _("(log is empty)"))
		self.textCtrl.SetInsertionPointEnd()

	def onExport(self, evt):
		with wx.FileDialog(
				self, _("Export log"), defaultDir=common.default_output_folder(),
				defaultFile="sarvamAI-log.txt",
				wildcard=_("Text files (*.txt)|*.txt"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write(logger.readLog(maxBytes=10 * 1024 * 1024))
			common.report(_("Log exported"))
		except Exception as ex:
			common.error_dialog(self, ex)

	def onClear(self, evt):
		if logger.clearLog():
			self._reload()
			common.report(_("Log cleared"))
