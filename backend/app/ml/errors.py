"""Exceptions raised by the ML pipeline (kept free of torch imports)."""


class InvalidScanError(Exception):
    """The scan cannot be segmented as uploaded (wrong dimensions, too large, ...)."""
