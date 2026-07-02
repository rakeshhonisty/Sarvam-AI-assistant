# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Add-on logging.

Messages go to NVDA's own log (with a clear ``Sarvam AI:`` prefix) and to a
dedicated file under the NVDA user configuration directory, which powers the
in-add-on log viewer and the export feature.

Important: NVDA ships a trimmed Python standard library that does **not**
include ``logging.handlers``. This module therefore avoids the ``logging``
package entirely for file output and does simple, thread-safe file writes with
manual size-based rotation, so the add-on always imports cleanly inside NVDA.
"""

import os
import time
import threading

import globalVars
from logHandler import log as nvdaLog

_PREFIX = "Sarvam AI: "
_LOG_FILENAME = "sarvamAI.log"
_MAX_BYTES = 512 * 1024

_lock = threading.Lock()
_debugEnabled = False


def _logDir():
	try:
		return globalVars.appArgs.configPath
	except Exception:
		return os.path.expanduser("~")


def logFilePath():
	"""Absolute path of the dedicated add-on log file."""
	return os.path.join(_logDir(), _LOG_FILENAME)


def setDebug(enabled):
	"""Enable or disable verbose debug logging."""
	global _debugEnabled
	_debugEnabled = bool(enabled)


def _rotate_if_needed(path):
	try:
		if os.path.getsize(path) > _MAX_BYTES:
			backup = path + ".1"
			try:
				if os.path.exists(backup):
					os.remove(backup)
				os.replace(path, backup)
			except OSError:
				# If rotation fails, truncate to avoid unbounded growth.
				open(path, "w", encoding="utf-8").close()
	except OSError:
		pass


def _write(level, msg):
	path = logFilePath()
	line = "%s %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), level, msg)
	with _lock:
		try:
			_rotate_if_needed(path)
			with open(path, "a", encoding="utf-8") as f:
				f.write(line)
		except Exception:
			# Never let logging break a feature.
			pass


def debug(msg):
	if _debugEnabled:
		try:
			nvdaLog.debug(_PREFIX + msg)
		except Exception:
			pass
		_write("DEBUG", msg)


def info(msg):
	try:
		nvdaLog.info(_PREFIX + msg)
	except Exception:
		pass
	_write("INFO", msg)


def warning(msg):
	try:
		nvdaLog.warning(_PREFIX + msg)
	except Exception:
		pass
	_write("WARNING", msg)


def error(msg, exc_info=False):
	try:
		nvdaLog.error(_PREFIX + msg, exc_info=exc_info)
	except Exception:
		pass
	_write("ERROR", msg)


def exception(msg):
	try:
		nvdaLog.error(_PREFIX + msg, exc_info=True)
	except Exception:
		pass
	# Capture the traceback into the dedicated file too.
	import traceback
	_write("ERROR", msg + "\n" + traceback.format_exc())


def readLog(maxBytes=200 * 1024):
	"""Return the tail of the dedicated log file for the in-add-on viewer."""
	path = logFilePath()
	try:
		size = os.path.getsize(path)
		with open(path, "r", encoding="utf-8", errors="replace") as f:
			if size > maxBytes:
				f.seek(size - maxBytes)
				f.readline()  # discard partial line
			return f.read()
	except FileNotFoundError:
		return ""
	except Exception as e:
		return "Could not read log file: %s" % e


def clearLog():
	try:
		open(logFilePath(), "w", encoding="utf-8").close()
		return True
	except Exception:
		return False
