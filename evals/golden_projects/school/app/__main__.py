"""Run the school app: `python -m evals.golden_projects.school.app --port 8765`.

`SCHOOL_BUGS=off` serves the PRD-correct build; the default (`on`) keeps the seeded bugs.
"""

from __future__ import annotations

import argparse

import uvicorn

from evals.golden_projects.school.app.web import bugs_from_env, create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="School golden app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(bugs_from_env()), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
