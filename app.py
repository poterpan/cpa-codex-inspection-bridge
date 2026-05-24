#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from cpa_inspection_bridge.config import DEFAULT_DATA_DIR, load_dotenv
from cpa_inspection_bridge.db import Database
from cpa_inspection_bridge.server import ControlServer
from cpa_inspection_bridge.service import BridgeService


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")

    parser = argparse.ArgumentParser(description="CPA Manager Codex inspection bridge")
    parser.add_argument("--host", default="127.0.0.1", help="control page host")
    parser.add_argument("--port", type=int, default=8766, help="control page port")
    parser.add_argument("--db", default=str(DEFAULT_DATA_DIR / "inspection_bridge.db"), help="SQLite database path")
    parser.add_argument("--once", action="store_true", help="run one inspection and exit")
    args = parser.parse_args()

    db = Database(Path(args.db))
    service = BridgeService(db)

    if args.once:
        run_id = service.run_once("manual")
        print(f"inspection run #{run_id} finished")
        return 0

    service.start_scheduler()
    server = ControlServer(args.host, args.port, db, service)

    def shutdown(_signum=None, _frame=None) -> None:
        service.stop_scheduler()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"CPA Manager inspection bridge is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown(None, None)
    finally:
        service.stop_scheduler()
    return 0


if __name__ == "__main__":
    sys.exit(main())
