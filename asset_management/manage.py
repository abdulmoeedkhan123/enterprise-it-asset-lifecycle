#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as error:
        raise ImportError(
            "Django is required. Install the application dependencies with "
            "`pip install -r asset_management/requirements.txt`."
        ) from error
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
