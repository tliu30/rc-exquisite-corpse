from io import BytesIO
import image_builder
import typing as t
import sqlite3
import json
from PIL import Image
from pillow_heif import register_heif_opener

from zulip_bots.lib import AbstractBotHandler

import form_parser
import rcprinter_client
import zulip_client
import db
from zulip_client import ZulipClient
from zulip_client import ZulipClientException
from zulip_client import ZulipMessage

register_heif_opener()

HELP_MESSAGE = """Thanks for playing the receipt printer exquisite corpse game!

You can interact with the bot using the following commands:
/start
/submit
/list
/print

or type anything to show this help message!
"""

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"

with db.get_connection() as conn:
    db.setup(conn)

RCPRINTER_CLIENT = rcprinter_client.RCPrinterClient()
ZULIP_CLIENT = ZulipClient('./zuliprc')


class GameBotHandler:
    """
    This is a bot for the receipt printer exquisite corpse game.
    """

    def _get_connection(self):
        return db.get_connection()

    def usage(self):
        return "This is a bot for a receipt printer exquisite corpse game"

    def handle_start(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        '''
        TO-DO:
        1) build the form image and save it as start_form.jpg
        2) write the array-to-bytes to feed into rcprinter
        3) call rcprinter
        4) send message
        '''
        

        sender_id = message.get("sender_id")  # int
        if sender_id is None:
            bot_handler.send_reply(message, "Error: Could not parse message to get sender_id")
            return

        conn = self._get_connection()

        game_id = db.create_game(conn, sender_id)
        drawing_id = db.init_drawing(conn, game_id, sender_id)
        print(f"Created game {game_id} and drawing {drawing_id}")

        drawing_id_for_form = db.convert_drawing_id_from_db_to_form(drawing_id)

        result = image_builder.build_titled_card("welcome", FONT_PATH, drawing_id_for_form)
        img = Image.fromarray(result, mode="L")
        fobj = BytesIO()
        img.save(fobj, format="jpeg")
        fobj.seek(0)
        RCPRINTER_CLIENT.send_image(fobj.read())

        bot_handler.send_reply(message, "Thanks for providing a start command!")

    def handle_submit(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        # Parse out image url, and fetch corresponding image
        attached_image_url = zulip_client.parse_image_url_from_message(message)
        if not attached_image_url:
            bot_handler.send_reply(message, "Error: no image; please include image in submission")
            return

        try:
            attached_image_bytes = ZULIP_CLIENT.get_image(attached_image_url)
        except ZulipClientException as e:
            bot_handler.send_reply(message, f"Error: issue with zulip client; {str(e)}")
            return
        except Exception as e:
            bot_handler.send_reply(message, f"Error: unable to fetch image; response {str(e)}")
            return

        # Parse the image
        try:
            attached_image = form_parser.get_opencv_image_from_bytes(attached_image_bytes)
        except Exception:
            bot_handler.send_reply(message, f"Error: unable to load image; perhaps unrecognized format")
            return

        try:
            parsed_drawing, labels = form_parser.parse_form(attached_image, 512)
        except form_parser.FormParserException as e:
            bot_handler.send_reply(message, f"Error: unable to parse form - please try a different picture; {str(e)}")
            return
        except Exception as e:
            bot_handler.send_reply(message, f"Error: unknown error in parsing form; {str(e)}")
            return

        bot_handler.send_reply(message, f"Success! Parsed drawing with ids {labels}")

        conn = self._get_connection()
        drawing_db_id = db.convert_drawing_id_from_form_to_db(
            (labels[1], labels[2], labels[3])
        )
        is_final = db.get_drawing_is_final(conn, drawing_db_id)
        print(f"Is final check: {is_final} for labels {labels} and drawing_db_id {drawing_db_id}")

        if not is_final:
            # Parse out mentioned user id, and get email so we can send a message to them
            mentioned_user_id = zulip_client.parse_mentioned_user_from_message(message)
            if not mentioned_user_id:
                bot_handler.send_reply(message, "Error: please include a tag of the next artist")
                return

            mentioned_user_email = ZULIP_CLIENT.get_email_for_user(mentioned_user_id)
            if not mentioned_user_email:
                bot_handler.send_reply(message, f"Error: could not get zulip email for mentioned user (id: {mentioned_user_id})")
                return

            game_id = db.get_game_id_for_drawing(conn, drawing_db_id)
            next_drawing_id = db.init_drawing(conn, game_id, message["sender_id"])
            
            parsed_drawing_as_bytes = form_parser.convert_opencv_image_to_bytes(parsed_drawing)
            db.submit_drawing(conn, drawing_db_id, parsed_drawing_as_bytes)

            next_drawing_id_for_form = db.convert_drawing_id_from_db_to_form(next_drawing_id)
            next_form = image_builder.build_titled_card("draw smthg!", FONT_PATH, next_drawing_id_for_form)
            # next_form_as_bytes = form_parser.convert_opencv_image_to_bytes(next_form)
            # RCPRINTER_CLIENT.send_image(next_form_as_bytes)

            img = Image.fromarray(next_form, mode="L")
            fobj = BytesIO()
            img.save(fobj, format="jpeg")
            fobj.seek(0)
            RCPRINTER_CLIENT.send_image(fobj.read())

            bot_handler.send_reply(
                message,
                "Success! Thanks for submitting. The next artist has been notified...",
            )
            bot_handler.send_message({
                "type": "private",
                "to": mentioned_user_email,
                "subject": "test message!",
                "content": "hi",
                }
            )
        else:
            parsed_drawing_as_bytes = form_parser.convert_opencv_image_to_bytes(parsed_drawing)
            db.submit_drawing(conn, drawing_db_id, parsed_drawing_as_bytes)

            # Also send a message to every other player...
            bot_handler.send_reply(
                message,
                "Success! Thanks for submitting. The game is done and ready to print!"
            )

    def handle_list(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        games_for_user = []
        data: list[tuple[str, str, str, int, int]] = []
        is_complete = lambda x: x > 1
        get_drawing_stats_for_game = lambda _: (1, 1)
        for game in games_for_user:
            n_submitted, n_total = get_drawing_stats_for_game(game)

            if is_complete(game):
                status = "completed"
            else:
                next_artist = get_next_artist_for_game(game)
                if next_artist == message["sender_id"]:
                    status = "waiting on you"
                else:
                    status = f"waiting on {next_artist}"

            data.append((
                game.id,
                status,
                str(game.last_updated_at),
                n_submitted,
                n_total,
            ))

        data = sorted(data, key=lambda x: x[2])


        msg = "\n".join([
            "You are part of the following games:",
            *(
                f"- {game_id}: {status} ({n_submitted} of {n_total}, last updated: {last_updated_at}"
                for (game_id, status, last_updated_at, n_submitted, n_total) in data
            ),
        ])

        bot_handler.send_reply(message, msg)

    def handle_print(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        content = message.get("content", "")
        args = content.split()

        if len(args) != 2:
            bot_handler.send_reply(message, "Usage: /print game_id")
            return

        conn = self._get_connection()
        game_id = int(args[1])
        is_complete = db.get_game_is_complete(conn, game_id)

        if is_complete:
            all_drawings = db.get_all_drawings_for_game(conn, game_id)
            form = image_builder.get_completed_game(all_drawings)
        else:
            next_drawing_data = db.get_next_drawing_for_game(conn, game_id)
            if next_drawing_data["artist_zulip_id"] == message["sender_id"]:
                lbls_ = db.convert_drawing_id_from_db_to_form(next_drawing_data["id"])
                form = image_builder.build_titled_card("draw smthg!", FONT_PATH, lbls_)
            else:
                bot_handler.send_reply(message, "This game is incomplete, and you are not next, so you may not print this form!")
                return

        img = Image.fromarray(form, mode="RGB").convert(mode="L")
        fobj = BytesIO()
        img.save(fobj, format="jpeg")
        fobj.seek(0)
        RCPRINTER_CLIENT.send_image(fobj.read())
        bot_handler.send_reply(message, "Success! Go check out the printer...")

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
