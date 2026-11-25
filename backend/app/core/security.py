"""Identifies the doctor making the current request."""

from flask import request, session


def current_doctor_id() -> str | None:
    """Return the id of the doctor making the request.

    Known limitation: the id is still accepted from the client (query string or form),
    so it is not a real authorization check. This is the single place to replace with
    server-side verification (Firebase ID token).
    """
    return (
        request.args.get("doctor_id")
        or request.form.get("doctor_id")
        or session.get("doctor_id")
    )
