"""Entry point: `python -m plane_fork_mcp [http|stdio]` (default http)."""

from __future__ import annotations

import os
import sys

import uvicorn

from plane_fork_mcp.server import build_http_app, build_server


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"
    if mode == "stdio":
        build_server().run(transport="stdio", show_banner=False)
        return
    if mode != "http":
        raise SystemExit(f"Unknown mode '{mode}': use 'http' or 'stdio'.")
    uvicorn.run(
        build_http_app(),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=os.getenv("ACCESS_LOG", "0") == "1",
    )


if __name__ == "__main__":
    main()
