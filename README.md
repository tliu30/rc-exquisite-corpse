Work in progress exquisite corpse game, to be played via receipt printer with
a zulip bot.

To see example snippets, run `uv install` and then `uv run jupyter lab`.

You may need to install `uv` first; you can do that on MacOS via `brew install uv`.

======

To test the bot, run `PYTHONPATH=. uv run zulip-botserver --config-file ./botserverrc`

You will need configuration secrets at
- botserverrc
- rcprinter.conf.json

You will need configuration secrets at the following environment variables
- DB_URI
- RCPRINTER_CSRF
- RCPRINTER_SESSION
- RCPRINTER_SESSION_SIG
- ZULIP_EMAIL
- ZULIP_API_KEY
- ZULIP_SITE
- ZULIP_TOKEN
- ZULIP_BOTSERVER_CONFIG
