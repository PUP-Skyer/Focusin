import atexit
import os
import tempfile

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["FOCUSIN_DB"] = os.path.join(TEST_DIR.name, "focusin-test.db")
atexit.register(TEST_DIR.cleanup)

import db


def init_db():
    db.init()
