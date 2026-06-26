import os
import json

# Assumes we are running from project root
PROJECT_ROOT = os.path.abspath(".")

DB_URI = os.environ.get("DB_URI")
FONT_PATH = os.path.join(PROJECT_ROOT, "fonts/Arial.ttf")

RCPRINTER_PRIVATE_KEY= os.environ["RCPRINTER_PRIVATE_KEY"]
