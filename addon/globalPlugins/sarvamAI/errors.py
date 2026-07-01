# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Typed exceptions for the Sarvam client and helpers to translate raw HTTP or
network failures into friendly, screen-reader-appropriate messages."""

import addonHandler

try:
	addonHandler.initTranslation()
except Exception:
	# initTranslation raises when not running inside NVDA (e.g. unit tests).
	pass


class SarvamError(Exception):
	"""Base class for all errors raised by the add-on's Sarvam layer.

	``message`` is safe to speak to the user. ``code`` is the machine code from
	the API when available, ``request_id`` aids support, ``status`` is the HTTP
	status code and ``retryable`` hints whether a retry might help.
	"""

	def __init__(self, message, code=None, request_id=None, status=None, retryable=False):
		super().__init__(message)
		self.message = message
		self.code = code
		self.request_id = request_id
		self.status = status
		self.retryable = retryable

	def __str__(self):
		return self.message


class AuthenticationError(SarvamError):
	"""Missing, invalid or unauthorised API key (HTTP 401/403)."""


class InsufficientCreditsError(SarvamError):
	"""The account has no credits left (HTTP 402)."""


class RateLimitError(SarvamError):
	"""Too many requests (HTTP 429)."""

	def __init__(self, message, retry_after=None, **kw):
		super().__init__(message, retryable=True, **kw)
		self.retry_after = retry_after


class InvalidRequestError(SarvamError):
	"""The request was malformed or a parameter was rejected (HTTP 400/422)."""


class ServerError(SarvamError):
	"""Sarvam returned a 5xx response."""

	def __init__(self, message, **kw):
		kw.setdefault("retryable", True)
		super().__init__(message, **kw)


class NetworkError(SarvamError):
	"""The request never reached Sarvam (DNS, TLS, connection, timeout)."""

	def __init__(self, message, **kw):
		kw.setdefault("retryable", True)
		super().__init__(message, **kw)


class CancelledError(SarvamError):
	"""The user cancelled a running operation."""


def error_from_status(status, payload, request_id=None):
	"""Build the right :class:`SarvamError` subclass from an HTTP response.

	``payload`` is the decoded JSON body (a dict) when parsing succeeded, else
	a plain string.
	"""
	code = None
	# Sarvam wraps errors as {"error": {"message": ..., "code": ..., "request_id": ...}}
	message = None
	if isinstance(payload, dict):
		err = payload.get("error")
		if isinstance(err, dict):
			message = err.get("message")
			code = err.get("code")
			request_id = err.get("request_id", request_id)
		elif isinstance(err, str):
			message = err
		if not message:
			message = payload.get("message") or payload.get("detail")
	elif isinstance(payload, str) and payload.strip():
		message = payload.strip()

	if not message:
		# Translators: generic server error with an HTTP status code.
		message = _("Sarvam returned HTTP status {status}.").format(status=status)

	common = dict(code=code, request_id=request_id, status=status)

	# Sarvam signals "no credits" as insufficient_quota_error, and returns it
	# with HTTP 402 on some services and 429 on others. Key off the code first.
	if code == "insufficient_quota_error":
		return InsufficientCreditsError(
			_("Your Sarvam account has no credits available. Add credits in the Sarvam dashboard. ({msg})").format(msg=message),
			**common)

	if status in (401, 403):
		# Translators: shown when the API key is rejected.
		return AuthenticationError(
			_("Authentication failed. Check your Sarvam API key in Settings. ({msg})").format(msg=message),
			**common)
	if status == 402:
		# Translators: shown when the Sarvam account has no credits.
		return InsufficientCreditsError(
			_("Your Sarvam account has no credits available. Add credits in the Sarvam dashboard. ({msg})").format(msg=message),
			**common)
	if status == 429:
		return RateLimitError(
			# Translators: shown when the API rate limit is hit.
			_("Rate limit reached. Please wait a moment and try again. ({msg})").format(msg=message),
			**common)
	if status in (400, 404, 415, 422):
		return InvalidRequestError(message, **common)
	if status >= 500:
		return ServerError(
			# Translators: shown for a Sarvam server-side error.
			_("Sarvam server error. Please try again shortly. ({msg})").format(msg=message),
			**common)
	return SarvamError(message, **common)
