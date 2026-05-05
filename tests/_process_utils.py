"""Cross-platform helpers for managing subprocess trees in tests.

``dapr run`` spawns ``daprd`` and the user's app as siblings; signaling only
the immediate process can orphan them if the signal isn't forwarded, which
leaves stale listeners on the test ports across runs. Putting the whole
subtree in its own group lets cleanup take them all down together.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any


def get_kwargs_for_process_group() -> dict[str, Any]:
    """Popen kwargs that place the child at the head of its own process group."""
    if sys.platform == 'win32':
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'start_new_session': True}


def terminate_process_group(proc: subprocess.Popen[str], *, force: bool = False) -> None:
    """Sends the right termination signal to an entire process group."""
    if sys.platform == 'win32':
        if force:
            proc.kill()
        else:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        return

    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except ProcessLookupError:
        pass
