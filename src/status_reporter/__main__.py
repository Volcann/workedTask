"""Enable python -m status_reporter execution."""

import sys

from status_reporter.cli import main

if __name__ == "__main__":
    sys.exit(main())
