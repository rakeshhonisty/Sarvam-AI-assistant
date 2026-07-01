# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Add-on logging.

Everything is written to NVDA's own log (so it shows up in NVDA's log viewer
with a clear ``Sarvam AI:`` prefix) and, additionally, to a dedicated rotating
file under the NVDA user configuration directory. The dedicated file powers the
in-add-on log viewer and the "export logs" feature, and works even when NVDA's
global log level is above debug.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

import globalVars
from logHandler import log as nvdaLog

_PREFIX = "Sarvam AI: "
_LOG_FILENAME = "sarvamAI.log"

_fileLogger = None
_debugEnabled = False


def _logDir():
	try:
		base = globalVars.appArgs.configPath
	except Exception:
		base = os.path.expanduser("~")
	return base


def logFilePath():
	"""Absolute path of the dedicated add-on log file."""
	return os.path.join(_logDir(), _LOG_FILENAME)


def _ensureFileLogger():
	global _fileLogger
	if _fileLogger is not None:
		return _fileLogger
	logger = logging.getLogger("sarvamAI")
	logger.setLevel(logging.DEBUG)
	logger.propagate = False
	try:
		handler = RotatingFileHandler(
			logFilePath(), maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
		handler.setFormatter(logging.Formatter(
			"%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
		logger.addHandler(handler)
	except Exception:
		# If the file cannot be opened we still log to NVDA's own log.
		pass
	_fileLogger = logger
	return logger


def setDebug(enabled):
	"""Enable or disable verbose debug logging."""
	global _debugEnabled
	_debugEnabled = bool(enabled)


def _write(level, msg, exc_info=False):
	try:
		_ensureFileLogger().log(level, msg, exc_info=exc_info)
	except Exception:
		pass


def debug(msg):
	if _debugEnabled:
		nvdaLog.debug(_PREFIX + msg)
		_write(logging.DEBUG, msg)


def info(msg):
	nvdaLog.info(_PREFIX + msg)
	_write(logging.INFO, msg)


def warning(msg):
	nvdaLog.warning(_PREFIX + msg)
	_write(logging.WARNING, msg)


def error(msg, exc_info=False):
	nvdaLog.error(_PREFIX + msg, exc_info=exc_info)
	_write(logging.ERROR, msg, exc_info=exc_info)


def exception(msg):
	nvdaLog.error(_PREFIX + msg, exc_info=True)
	_write(logging.ERROR, msg, exc_info=True)


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
