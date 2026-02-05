#!/usr/bin/env python3
"""Run the FastAPI server."""

import sys

sys.path.insert(0, "/app" if sys.argv[0].startswith("/app") else ".")

import uvicorn

from config.settings import API_HOST, API_PORT
from src.utils.logger import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(
        "src.api.app:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
