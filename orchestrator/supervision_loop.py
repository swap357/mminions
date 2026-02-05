from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from .tmux_supervisor import TmuxSupervisor


@dataclass
class WorkerWatchState:
    session_name: str
    script_path: Path
    stalled_once: bool = False
    restarted_once: bool = False
    last_digest: str = ""
    last_change_epoch: float = 0.0
    failed: bool = False


class SupervisionLoop:
    def __init__(self, tmux: TmuxSupervisor, stall_timeout_sec: int = 90) -> None:
        self.tmux = tmux
        self.stall_timeout_sec = stall_timeout_sec

    def tick(self, state: WorkerWatchState, workdir: Path) -> WorkerWatchState:
        if state.failed:
            return state

        if not self.tmux.session_exists(state.session_name):
            return state

        pane = self.tmux.capture_pane(state.session_name, lines=200)
        digest = pane[-500:]
        now_epoch = time.time()

        if state.last_change_epoch == 0.0:
            state.last_change_epoch = now_epoch

        if digest != state.last_digest:
            state.last_digest = digest
            state.last_change_epoch = now_epoch
            return state

        stalled_for = now_epoch - state.last_change_epoch
        if stalled_for < self.stall_timeout_sec:
            return state

        if not state.stalled_once:
            self.tmux.send_text(state.session_name, "status update: report progress or current blocker")
            state.stalled_once = True
            state.last_change_epoch = now_epoch
            return state

        if not state.restarted_once:
            self.tmux.kill_session(state.session_name)
            self.tmux.create_session(
                name=state.session_name,
                workdir=workdir,
                command=str(state.script_path),
            )
            state.restarted_once = True
            state.last_change_epoch = now_epoch
            return state

        state.failed = True
        self.tmux.kill_session(state.session_name)
        return state
