# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Run blocking Sarvam calls off NVDA's main thread.

NVDA's GUI runs on the wx main loop; any network work must happen on a worker
thread and deliver its result back via :func:`wx.CallAfter`. :func:`run_task`
wraps that pattern together with a cancellable, accessible progress dialog.
"""

import threading

import wx
import gui
import addonHandler

from . import client
from . import errors
from . import logger

addonHandler.initTranslation()


class _ProgressDialog(wx.Dialog):
	"""A minimal, fully accessible modeless progress dialog with Cancel.

	We deliberately avoid ``wx.ProgressDialog`` because its cancel button
	behaviour and screen-reader announcements are inconsistent across
	platforms. This custom dialog exposes a labelled gauge and a status label
	whose text is announced when it changes.
	"""

	def __init__(self, parent, title, message, cancel_token):
		super().__init__(parent, title=title)
		self._cancel = cancel_token
		main = wx.BoxSizer(wx.VERTICAL)
		self._status = wx.StaticText(self, label=message)
		main.Add(self._status, border=10, flag=wx.ALL | wx.EXPAND)
		self._gauge = wx.Gauge(self, range=100, size=(320, 20))
		self._gauge.Pulse()
		main.Add(self._gauge, border=10, flag=wx.ALL | wx.EXPAND)
		self._cancelBtn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		self._cancelBtn.Bind(wx.EVT_BUTTON, self._onCancel)
		main.Add(self._cancelBtn, border=10, flag=wx.ALL | wx.ALIGN_RIGHT)
		self.Bind(wx.EVT_CLOSE, self._onCancel)
		self.SetSizerAndFit(main)
		self.CentreOnScreen()

	def _onCancel(self, evt):
		if self._cancel:
			self._cancel.cancel()
		self._status.SetLabel(_("Cancelling..."))
		self._cancelBtn.Enable(False)

	def setProgress(self, done, total):
		if total:
			pct = int(done * 100 / total)
			self._gauge.SetValue(min(100, max(0, pct)))
		else:
			self._gauge.Pulse()

	def setStatus(self, text):
		self._status.SetLabel(text)


def run_task(func, on_success=None, on_error=None, title=None, message=None,
		parent=None, with_progress=True):
	"""Execute ``func(cancel, progress)`` on a worker thread.

	``func`` receives a :class:`~.client.CancelToken` and a ``progress(done,
	total)`` callback (safe to call from the worker). ``on_success(result)`` and
	``on_error(exception)`` run on the main thread. Returns the cancel token so
	callers may cancel programmatically.
	"""
	cancel = client.CancelToken()
	parent = parent or (gui.mainFrame if gui and hasattr(gui, "mainFrame") else None)
	dlg = None
	if with_progress and parent is not None:
		dlg = _ProgressDialog(parent, title or _("Sarvam AI"),
			message or _("Working..."), cancel)
		dlg.Show()

	def progress(done, total):
		if dlg:
			wx.CallAfter(dlg.setProgress, done, total)

	def worker():
		try:
			result = func(cancel, progress)
		except errors.CancelledError:
			logger.debug("Task cancelled by user.")
			wx.CallAfter(_finish, dlg, None)
			return
		except errors.SarvamError as e:
			logger.warning("Task failed: %s" % e.message)
			wx.CallAfter(_finish, dlg, None)
			if on_error:
				wx.CallAfter(on_error, e)
			return
		except Exception as e:  # noqa: BLE001 - surface unexpected errors safely
			logger.exception("Unexpected task error")
			wrapped = errors.SarvamError(_("Unexpected error: {err}").format(err=e))
			wx.CallAfter(_finish, dlg, None)
			if on_error:
				wx.CallAfter(on_error, wrapped)
			return
		wx.CallAfter(_finish, dlg, None)
		if on_success:
			wx.CallAfter(on_success, result)

	threading.Thread(target=worker, name="SarvamAITask", daemon=True).start()
	return cancel


def _finish(dlg, _unused):
	if dlg:
		try:
			dlg.Destroy()
		except Exception:
			pass
