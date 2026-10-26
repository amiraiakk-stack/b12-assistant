"""Command line: python -m b12 <command>

  login      open a browser and sign in to B12 once (session is saved)
  discover   save screenshots/HTML of B12 pages to data/discover, for setting up selectors.json
  sync       fetch new B12 messages and extract tasks
  ask "..."  ask a question, e.g. python -m b12 ask "شو عنا بكرا؟"
  serve      run the web page (and the WhatsApp bot if configured) with background sync
"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    command, args = sys.argv[1], sys.argv[2:]
    if command == "login":
        from .scraper import login

        login()
    elif command == "discover":
        from .scraper import discover

        discover()
    elif command == "sync":
        from .assistant import sync_and_process

        print(sync_and_process())
    elif command == "ask":
        from .assistant import ask

        print(ask(" ".join(args) or "شو عنا بكرا؟"))
    elif command == "serve":
        import uvicorn

        uvicorn.run("b12.web:app", host="127.0.0.1", port=8000)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
