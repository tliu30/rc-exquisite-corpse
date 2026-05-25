import typing as t
import json

from zulip_bots.lib import AbstractBotHandler

ZulipMessage = dict[str, t.Any]

HELP_MESSAGE = """Thanks for playing the receipt printer exquisite corpse game!

You can interact with the bot using the following commands:
/start
/submit
/list
/print

or type anything to show this help message!
"""

def get_attached_image(relative_image_url: str) -> bytes:
    from zulip import Client
    c = Client(config_file='./zuliprc')
    full_url = f"{c.base_url}{relative_image_url}"
    response = c.session.get(full_url) 
    return response.content # this is the image in bytes

class GameBotHandler:
    """
    This is a bot for the receipt printer exquisite corpse game.
    """

    def usage(self):
        return "This is a bot for a receipt printer exquisite corpse game"

    def handle_start(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a start command!")

    def handle_submit(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        message_as_str = json.dumps(message)
        bot_handler.send_reply(
            message,
            f"Thanks for providing a submit command! Original message: {message_as_str}"
        )

    def handle_list(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a list command!")

    def handle_print(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a print command!")

    def show_help(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, HELP_MESSAGE)
    
    def handle_message(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        content = message.get("content", "")

        args = content.split(" ")

        command = args[0] if args else "(missing)"

        match command:
            case "/start":
                return self.handle_start(message, bot_handler)
            
            case "/submit":
                return self.handle_submit(message, bot_handler)

            case "/list":
                return self.handle_list(message, bot_handler)

            case "/print":
                return self.handle_print(message, bot_handler)

            case _:
                return self.show_help(message, bot_handler)

handler_class = GameBotHandler
