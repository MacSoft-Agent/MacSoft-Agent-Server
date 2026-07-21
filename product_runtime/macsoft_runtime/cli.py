from __future__ import annotations

import argparse
import signal
import threading
from pathlib import Path

from .control import HostControlServer
from .host import prepare_host
from .metadata import load_product_metadata
from .paths import resolve_development_paths, resolve_packaged_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="macsoft-host")
    parser.add_argument("--mode", choices=("development", "packaged"), default="packaged")
    parser.add_argument("--program-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--control-port", type=int, default=8766)
    parser.add_argument("--initialize-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = (
        resolve_development_paths(args.program_root)
        if args.mode == "development"
        else resolve_packaged_paths(args.program_root, args.data_root)
    )
    metadata = load_product_metadata(paths.program_root)
    host = prepare_host(paths, metadata)
    if args.initialize_only:
        return 0
    host.acquire()
    control = HostControlServer(host, args.control_port)
    stopped = threading.Event()

    def request_stop(*_args: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        host.start_all()
        control.start()
        stopped.wait()
    finally:
        control.stop()
        host.stop_all()
        host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
