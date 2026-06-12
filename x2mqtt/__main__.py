import logging
import sys

from .app import App
from .const import *

if __name__ == "__main__":
    app = App.create()
    log = logging.getLogger(app.app_name)

    if app.verbose:
        if app.verbose >= 4:
            level = logging.DEBUG
        elif app.verbose >= 3:
            log.setLevel(logging.DEBUG)
            level = logging.INFO
        elif app.verbose >= 2:
            level = logging.INFO
        elif app.verbose >= 1:
            level = logging.WARNING

        logging.basicConfig(level=level, format=app.log_format)

    try:
        sys.exit(app())
    except Exception as exc:
        log.exception(exc)
        sys.exit(1)
