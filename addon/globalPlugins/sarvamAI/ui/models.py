# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Model switching (the Model Center).

One place to choose the model behind every Sarvam feature. For each service
there is a model list and a read-only description that says what the chosen
model is good at, how much it can read at once, whether it sees images and how
it reasons. "Check which models my key can use" asks Sarvam for the models
available to the user's key and marks them.

Tab order: service combo, description, next service ... then Check, Save,
Close. Changing a combo speaks the description at once.
"""

import wx
import gui
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import config
from .. import client
from .. import models
from .. import tasks
from . import common


class ModelCenterDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the model switching dialog.
		super().__init__(parent, title=_("Sarvam AI - Model switching"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._available = None
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		helper.addItem(wx.StaticText(self, label=_(
			"Choose the Sarvam model used by each feature. The description below each "
			"list explains the selected model.")))
		self._rows = []
		for key, label, catalogue, default, cfg_key in models.SERVICES:
			ids = [m["id"] for m in catalogue]
			ctrl = helper.addLabeledControl(_(label) + ":", wx.Choice,
				choices=[models.label_of(key, i) for i in ids])
			current = conf.get(cfg_key) or default
			common.select_in_combo(ctrl, ids, current if current in ids else default)
			desc = helper.addLabeledControl(
				_("About this model:"), wx.TextCtrl,
				style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL, size=(560, 54))
			row = dict(key=key, ids=ids, ctrl=ctrl, desc=desc, cfg=cfg_key)
			ctrl.Bind(wx.EVT_CHOICE, lambda e, r=row: self._onChange(r, speak=True))
			self._rows.append(row)
			self._onChange(row)

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: asks Sarvam which chat models the user's key can use.
		self.checkBtn = btns.addButton(self, label=_("C&heck which models my key can use"))
		self.checkBtn.Bind(wx.EVT_BUTTON, self.onCheck)
		saveBtn = btns.addButton(self, label=_("&Save"))
		saveBtn.Bind(wx.EVT_BUTTON, self.onSave)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self._rows[0]["ctrl"].SetFocus()

	def _selected(self, row):
		return row["ids"][max(0, row["ctrl"].GetSelection())]

	def _onChange(self, row, speak=False):
		mid = self._selected(row)
		text = models.describe(row["key"], mid)
		if self._available is not None and row["key"] in ("chat", "vision"):
			text += " " + (_("Available to your key.") if mid in self._available
				else _("Not listed for your key."))
		row["desc"].ChangeValue(text)
		if speak:
			common.report(text)

	def onCheck(self, evt):
		self.checkBtn.Enable(False)

		def ok(ids):
			self.checkBtn.Enable(True)
			self._available = set(ids)
			for row in self._rows:
				if row["key"] in ("chat", "vision"):
					labels = []
					for i in row["ids"]:
						lab = models.label_of(row["key"], i)
						if i not in self._available:
							# Translators: marks a model the key cannot use.
							lab += " " + _("(not available)")
						labels.append(lab)
					sel = row["ctrl"].GetSelection()
					row["ctrl"].Set(labels)
					row["ctrl"].SetSelection(sel)
				self._onChange(row)
			usable = [i for i in models.chat_ids() if i in self._available]
			common.report(_("{n} of {total} chat models are available to your key.").format(
				n=len(usable), total=len(models.chat_ids())))

		def bad(exc):
			self.checkBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(lambda cancel, progress: self._cli.list_models(cancel=cancel),
			on_success=ok, on_error=bad, title=_("Sarvam AI"),
			message=_("Asking Sarvam which models your key can use..."), parent=self)

	def onSave(self, evt):
		conf = config.conf()
		for row in self._rows:
			conf[row["cfg"]] = self._selected(row)
		# Keep the reasoning effort valid for the newly chosen chat model.
		chat = conf.get("chatModel")
		conf["reasoningEffort"] = models.normalise_effort(chat, conf.get("reasoningEffort"))
		common.report(_("Models saved"))
		self.Close()


def cycle_chat_model(step=1):
	"""Switch to the next chat model and return its spoken description."""
	conf = config.conf()
	ids = list(models.chat_ids())
	cur = conf.get("chatModel")
	i = ids.index(cur) if cur in ids else 0
	new = ids[(i + step) % len(ids)]
	conf["chatModel"] = new
	conf["reasoningEffort"] = models.normalise_effort(new, conf.get("reasoningEffort"))
	return _("Chat model: {label}").format(label=models.chat_label(new))
