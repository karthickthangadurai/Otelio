"""Helpers to hide emails and names before writing logs."""

import re

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def mask_email(email):
    """Turn an email into something like k***@gmail.com for logs."""
    if not email or "@" not in email:
        return "***"

    local, domain = email.split("@", 1)
    if not local:
        return "***@" + domain
    return local[0] + "***@" + domain


def mask_payload(obj):
    """Walk a dict/list/string and mask anything that looks like PII.

    Hint for later:
    - dict  -> check each key; mask "email" / "guest_name", recurse on the rest
    - list  -> mask each item the same way
    - str   -> find emails in the text with EMAIL_RE and mask them
    - other -> leave as-is (numbers, bools, None, …)
    Used only for logging — real data in the DB / tools stays unchanged.
    """

    if isinstance(obj, dict):
        masked = {}
        for key, value in obj.items():
            if key == "email" and isinstance(value, str):
                masked[key] = mask_email(value)
            elif key in ("guest_name", "name") and isinstance(value, str) and value:
                masked[key] = value[0] + "***"
            else:
                masked[key] = mask_payload(value)
        return masked

    if isinstance(obj, list):
        return [mask_payload(item) for item in obj]

    if isinstance(obj, str):
        # replace any email that appears inside free text
        return EMAIL_RE.sub(lambda m: mask_email(m.group(0)), obj)

    return obj
