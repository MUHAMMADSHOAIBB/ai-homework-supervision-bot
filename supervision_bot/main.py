"""
main.py — Start the AI Homework Supervision Bot

Usage:
  python main.py                    # Start with default child profile
  python main.py --name 小明 --age 10
  python main.py --debug            # Show camera feed with debug overlay
  python main.py --api-only         # Start API server without CV pipeline (for testing)
"""
import asyncio
import argparse
import sys

import config  # imports Windows asyncio policy fix on win32

import uvicorn
from logic.session_manager import SessionManager
from api.server import app, set_session_manager
from data.db import Database


async def main():
    parser = argparse.ArgumentParser(description="AI Homework Supervision Bot")
    parser.add_argument("--name",     default=config.CHILD_NAME,  help="Child's name")
    parser.add_argument("--age",      type=int, default=config.CHILD_AGE, help="Child's age")
    parser.add_argument("--debug",    action="store_true", help="Show camera debug overlay")
    parser.add_argument("--api-only", action="store_true", dest="api_only",
                        help="Start API server only (no camera)")
    args = parser.parse_args()

    # Override config defaults from CLI
    config.CHILD_NAME = args.name
    config.CHILD_AGE  = args.age

    db = Database()
    await db.init()

    session_manager = SessionManager(debug=args.debug, api_only=args.api_only)
    session_manager.db = db
    set_session_manager(session_manager)

    print(f"[Bot] Starting — child: {args.name}, age: {args.age}, debug: {args.debug}")
    print(f"[Bot] API:       http://{config.API_HOST}:{config.API_PORT}")
    print(f"[Bot] Dashboard: http://{config.API_HOST}:{config.API_PORT}/dashboard")
    print(f"[Bot] Press Ctrl+C to stop.")

    # Configure uvicorn server
    uv_config = uvicorn.Config(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(uv_config)

    if args.api_only:
        await server.serve()
    else:
        # Start FastAPI in background, run CV pipeline in foreground
        api_task = asyncio.create_task(server.serve())
        cv_task  = asyncio.create_task(session_manager.run())
        try:
            await asyncio.gather(api_task, cv_task)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[Bot] Shutting down...")
            server.should_exit = True
            session_manager.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bot] Stopped.")
