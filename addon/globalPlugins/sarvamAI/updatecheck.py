# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Very small, optional update check against the GitHub Releases API.

This never blocks NVDA: the network request runs on a worker thread and results
are reported on the main thread. If the repository has no releases yet, or the
machine is offline, it fails quietly (or informs the user when run
interactively)."""

import json
import urllib.request
import urllib.error

import wx
import gui
import addonHandler

from . import constants
from . import config
from . import logger

addonHandler.initTranslation()

# Update the owner/repo once the GitHub repository is published.
GITHUB_OWNER = "your-github-username"
GITHUB_REPO = "SarvamAIAddon"
RELEASES_API = "https://api.github.com/repos/%s/%s/releases/latest"


def _current_version():
	try:
		for addon in addonHandler.getRunningAddons():
			if addon.name == constants.ADDON_NAME:
				return addon.version
	except Exception:
		pass
	return "1.0.0"


def _fetch_latest():
	url = RELEASES_API % (GITHUB_OWNER, GITHUB_REPO)
	req = urllib.request.Request(url, headers={
		"Accept": "application/vnd.github+json",
		"User-Agent": "SarvamAI-NVDA-Addon",
	})
	with urllib.request.urlopen(req, timeout=15) as resp:
		data = json.loads(resp.read().decode("utf-8"))
	tag = (data.get("tag_name") or "").lstrip("vV")
	return tag, data.get("html_url")


def check(parent=None, interactive=False):
	"""Check for a newer release. When ``interactive`` is False, stay silent
	unless a newer version exists."""
	import threading

	def worker():
		try:
			latest, url = _fetch_latest()
		except Exception as e:
			logger.debug("Update check failed: %s" % e)
			if interactive:
				wx.CallAfter(gui.messageBox,
					_("Could not check for updates. Please try again later."),
					_("Sarvam AI - Updates"), wx.OK | wx.ICON_INFORMATION, parent)
			return
		current = _current_version()
		if latest and _is_newer(latest, current):
			def prompt():
				if gui.messageBox(
						_("A new version {latest} is available (you have {current}).\n"
							"Open the download page?").format(latest=latest, current=current),
						_("Sarvam AI - Update available"),
						wx.YES | wx.NO | wx.ICON_INFORMATION, parent) == wx.YES and url:
					import os
					os.startfile(url)
			wx.CallAfter(prompt)
		elif interactive:
			wx.CallAfter(gui.messageBox,
				_("You are using the latest version ({current}).").format(current=current),
				_("Sarvam AI - Updates"), wx.OK | wx.ICON_INFORMATION, parent)

	threading.Thread(target=worker, name="SarvamAIUpdateCheck", daemon=True).start()


def _is_newer(latest, current):
	def parse(v):
		parts = []
		for p in str(v).replace("-", ".").split("."):
			try:
				parts.append(int(p))
			except ValueError:
				parts.append(0)
		return tuple(parts)
	try:
		return parse(latest) > parse(current)
	except Exception:
		return False


def maybe_check_on_start(parent=None):
	if config.conf().get("checkForUpdates") and GITHUB_OWNER != "your-github-username":
		check(parent, interactive=False)
