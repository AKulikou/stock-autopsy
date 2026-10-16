"""
Start the web UI on this machine only:

    python -m web            # http://127.0.0.1:8001
    python -m web --port 8080
"""

import argparse
import logging
from datetime import datetime

import uvicorn
from dotenv import load_dotenv

HOST = "127.0.0.1"  # never 0.0.0.0: the API key in .env pays for every run

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock Autopsy web UI (local only)")
    parser.add_argument("--port", type=int, default=8001)  # Startup Autopsy uses 8000
    port = parser.parse_args().port
    load_dotenv(override=True)

    from main import setup_logging
    from web.app import create_app

    log_file = setup_logging(datetime.now().strftime("%Y%m%d_%H%M%S"))
    logger.info(f"Stock Autopsy web UI: http://{HOST}:{port}  (Ctrl+C to stop; log: {log_file})")
    uvicorn.run(create_app(), host=HOST, port=port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
