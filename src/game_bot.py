import typing as t
import json

from zulip_bots.lib import AbstractBotHandler

import form_parser
import zulip_client
from zulip_client import ZulipClient
from zulip_client import ZulipMessage

HELP_MESSAGE = """Thanks for playing the receipt printer exquisite corpse game!

You can interact with the bot using the following commands:
/start
/submit
/list
/print

or type anything to show this help message!
"""


ZULIP_CLIENT = ZulipClient('./zuliprc')


class GameBotHandler:
    """
    This is a bot for the receipt printer exquisite corpse game.
    """

    def usage(self):
        return "This is a bot for a receipt printer exquisite corpse game"

    def handle_start(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a start command!")

    def handle_submit(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        # NEXT TO DOS
        # - mentioned user id only sometime required; do all image processing first
        # - need database calls; reconstructing id from the labels
        # - side effects: message next, reply, handle errors, write image to db / do updates

        # Parse out mentioned user id, and get email so we can send a message to them
        # mentioned_user_id = zulip_client.parse_mentioned_user_from_message(message)
        # if not mentioned_user_id:
        #     return

        # mentioned_user_email = ZULIP_CLIENT.get_email_for_user(mentioned_user_id)
        # if not mentioned_user_email:
        #     return

        # Parse out image url, and fetch corresponding image
        attached_image_url = zulip_client.parse_image_url_from_message(message)
        if not attached_image_url:
            return

        attached_image_bytes = ZULIP_CLIENT.get_image(attached_image_url)
        if not attached_image_bytes:
            return

        # Parse the image
        try:
            attached_image = form_parser.get_opencv_image_from_bytes(attached_image_bytes)
            parsed_drawing, labels = form_parser.parse_form(attached_image, 512)

            from PIL import Image
            new_image = form_parser.convert_opencv_to_pil(parsed_drawing)
            new_image.save("result.jpg")
            print(parsed_drawing, labels)
        except Exception:
            return

        message_as_str = json.dumps(message)
        bot_handler.send_reply(
            message,
            f"Thanks for providing a submit command! Original message: {message_as_str}"
        )

        # bot_handler.send_message({
        #     "type": "private",
        #     "to": mentioned_user_email,
        #     "subject": "test message!",
        #     "content": "hi",
        #     }
        # )

    def handle_list(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a list command!")

    def handle_print(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, "Thanks for providing a print command!")

    def show_help(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        bot_handler.send_reply(message, HELP_MESSAGE)
    
    def handle_message(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        content = message.get("content", "")

        args = content.split()

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
