from __future__ import annotations

import os
import re


_OTP_MOCK_LOG = "/tmp/zaska-otp.log"


def get_register_otp(email: str) -> str:
    """Return OTP code for email from the mock log file (dev/mock mode only).

    The file is written by the logger when OTP_PROVIDER=mock and is never stored in Redis.
    """
    target = email.strip().lower()
    pattern = re.compile(r"\[OTP MOCK\] Code for " + re.escape(target) + r": (\d{6})", re.IGNORECASE)

    if not os.path.exists(_OTP_MOCK_LOG):
        raise AssertionError(
            f"OTP log file {_OTP_MOCK_LOG} not found. "
            "Ensure OTP_PROVIDER=mock and ENV != production."
        )

    with open(_OTP_MOCK_LOG) as f:
        lines = f.readlines()

    for line in reversed(lines):
        m = pattern.search(line)
        if m:
            return m.group(1)

    raise AssertionError(
        f"No OTP found for {email} in {_OTP_MOCK_LOG}. "
        "Register may have used smtp mode or log was rotated."
    )
