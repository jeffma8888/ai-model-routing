"""Allow ``python -m model_routing``."""

import sys

from .cli import main

sys.exit(main())
