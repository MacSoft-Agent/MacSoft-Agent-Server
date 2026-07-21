from __future__ import annotations

import os
import threading
from pathlib import Path

import win32event
import win32service
import win32serviceutil

from .control import HostControlServer
from .host import prepare_host
from .metadata import load_product_metadata
from .paths import resolve_packaged_paths


class MacSoftAgentHostService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MacSoftAgentHost"
    _svc_display_name_ = "MacSoft Agent Host"
    _svc_description_ = "Runs the MacSoft Agent AI Service and MacSoft Server."

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.host = None
        self.control = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self) -> None:
        program_root = Path(os.environ.get("MACSOFT_PROGRAM_ROOT", Path(__file__).resolve().parents[1]))
        paths = resolve_packaged_paths(program_root)
        metadata = load_product_metadata(paths.program_root)
        self.host = prepare_host(paths, metadata)
        self.host.acquire()
        self.control = HostControlServer(self.host)
        try:
            self.host.start_all()
            self.control.start()
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        finally:
            if self.control:
                self.control.stop()
            if self.host:
                self.host.stop_all()
                self.host.close()


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(MacSoftAgentHostService)
