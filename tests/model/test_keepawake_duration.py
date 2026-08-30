"""Opt-in verification that sleep prevention actually holds past the idle-sleep threshold.

`SetThreadExecutionState` returning non-zero proves the call was accepted, not that Windows
honoured it — and on Modern Standby systems the distinction is real. This test holds the
request longer than the machine's own idle-sleep timeout and then checks the Windows System
event log for standby-entry events during that window.

**Marked `slow` and skipped by default.** It takes longer than the sleep threshold (11 minutes
on a default Windows AC profile) and is pointless in CI. Run it explicitly when validating a
new machine — particularly before S12, where a multi-hour training run depends on this:

    uv run pytest tests/model/test_keepawake_duration.py -m slow --run-slow -s

Production evidence already recorded (see PROJECT_STATUS.md): on 2026-08-30 the reBEN
extraction ran a continuous 616.9 s pass on AC power, past the machine's 10-minute threshold,
with zero standby events — while an earlier identical-workload run *without* keep_awake was
killed by Modern Standby at 06:50. Same I/O, same idleness; the only difference was the
power request.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime

import pytest

from satquery.utils.keepawake import keep_awake

pytestmark = [pytest.mark.slow, pytest.mark.model]

#: Longer than the default Windows AC idle-sleep timeout (600 s) with margin.
HOLD_SECONDS = 660

#: System-log event ids: 42 = entering sleep, 506/507 = Modern Standby enter/exit,
#: 107 = resume from sleep, 1 (Power-Troubleshooter source) = wake.
SLEEP_EVENT_IDS = (42, 107, 506, 507)


def _sleep_events_since(started: datetime) -> list[str]:
    """Return System-log sleep/standby events recorded since ``started``."""
    ids = ",".join(str(i) for i in SLEEP_EVENT_IDS)
    script = (
        f"$s=[datetime]::Parse('{started.isoformat()}');"
        f"$e=Get-WinEvent -FilterHashtable @{{LogName='System';StartTime=$s;Id={ids}}} "
        f"-ErrorAction SilentlyContinue;"
        f"if($e){{$e|ForEach-Object{{\"$($_.TimeCreated) $($_.Id)\"}}}}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows idle-sleep behaviour")
def test_prevention_holds_past_the_sleep_threshold() -> None:
    """Hold the request past the idle-sleep timeout; assert no standby event fires."""
    started = datetime.now(UTC).astimezone()

    with keep_awake("keepawake duration verification") as active:
        assert active is True, "sleep prevention did not activate"
        deadline = time.monotonic() + HOLD_SECONDS
        while time.monotonic() < deadline:
            # Idle deliberately: no input, minimal CPU. Windows idle-sleep keys on the absence
            # of user input, so busy-looping here would confound the test.
            time.sleep(5)

    events = _sleep_events_since(started)
    assert not events, (
        f"machine entered standby during a {HOLD_SECONDS}s keep_awake hold: {events}. "
        "Sleep prevention is NOT effective on this hardware — a long run will be killed."
    )
