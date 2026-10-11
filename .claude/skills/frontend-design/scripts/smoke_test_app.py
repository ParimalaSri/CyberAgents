"""Smoke-test a Streamlit app headlessly: it must run without exceptions and render content."""
import argparse
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

DEFAULT_TIMEOUT = 30


def main():
    """Run the app with Streamlit's test runner and report exceptions and widget counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default="app/streamlit_app.py")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    app = AppTest.from_file(str(Path(args.app).resolve()), default_timeout=args.timeout).run()
    print(f"app: {args.app}")
    print(f"titles={len(app.title)} dataframes={len(app.dataframe)} "
          f"selectboxes={len(app.selectbox)} sliders={len(app.slider)} buttons={len(app.button)}")
    if app.exception:
        print("FAIL: the app raised exceptions:")
        for exc in app.exception:
            print(f"- {exc.value}")
        sys.exit(1)
    if not (app.title or app.header or app.markdown):
        print("FAIL: the app rendered no title, header or text")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
