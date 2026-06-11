import os
import json

# Assumes we are running from project root
PROJECT_ROOT = os.path.abspath(".")

config = None
with open(os.path.join(PROJECT_ROOT, "game.conf.json")) as f:
    config = json.load(f)

if not config:
    raise Exception("Could not load game config from game.conf.json")

DB_URI = config.get("DB_URI")
FONT_PATH = config.get("FONT_PATH")
RCPRINTER_CONF_PATH = os.path.join(PROJECT_ROOT, 'rcprinter.conf.json')
ZULIP_CONF_PATH = os.path.join(PROJECT_ROOT, 'zuliprc')
