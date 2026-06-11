import logging
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
import consts
import config
from zulip_client import ZulipClient
from zulip_client import ZulipClientException
from zulip_client import ZulipMessage

logger = logging.getLogger(__name__)

register_heif_opener()

HELP_MESSAGE = """Hi, I'm the RC Exquisite Corpse game bot - thanks for playing!

**Commands**
- `/start` - start a new game!
- `/submit {attached-image} {@next-artist}` - submit your drawing (you can just take a picture!), and choose the next artist by tagging them in Zulip
- `/print` - print out forms or completed games that you've been part of
- `/list` - list the games that you are part of
- `/help` - show this message

**How to play**

In an exquisite corpse game, players create a collaborative work of art. Each player continues from where the last artist left off - but they don't get to see what the last artist drew, making for fun surprises.

This version of the game uses forms that are printed out from the receipt printer in the hub for some RC-specific fun. We also provide the image files so you can participate remotely, too!

Look at the top of your frame to see where the last drawing ended, and make sure to draw all the way to the bottom so the following artist can continue.

Here is an [example](https://mrdeyo.com/wp-content/uploads/2021/11/maxresdefault.jpg) of a completed game.
"""

with db.get_connection() as conn:
    db.setup(conn)

RCPRINTER_CLIENT = rcprinter_client.RCPrinterClient(conf_path=config.RCPRINTER_CONF_PATH)
ZULIP_CLIENT = ZulipClient(config.ZULIP_CONF_PATH)


class GameBotHandler:
    """
    This is a bot for the receipt printer exquisite corpse game.
    """

    def _get_connection(self):
        return db.get_connection()

    def usage(self):
        return "This is a bot for a receipt printer exquisite corpse game"

    def handle_start(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        sender_id = message.get("sender_id")  # int
        if sender_id is None:
            bot_handler.send_reply(message, "Error: Could not parse message to get sender_id")
            return

        sender_name = ZULIP_CLIENT.get_name_for_user(sender_id)
        if sender_name is None:
            bot_handler.send_reply(message, "Error: Could not get name for sender")
            return

        conn = self._get_connection()

        game_id = db.create_game(conn, sender_id, length=3)
        drawing_id = db.init_drawing(conn, game_id, sender_id)
        logger.info(f"Created game {game_id} and drawing {drawing_id}")

        drawing_id_for_form = db.convert_drawing_id_from_db_to_form(drawing_id)

        result = image_builder.build_start_form(
            drawing_id_for_form,
            sender_name,
        )
        img = Image.fromarray(result, mode="L")
        RCPRINTER_CLIENT.send_image(img)

        try:
            upload_url = ZULIP_CLIENT.upload_image(img)
            bot_handler.send_reply(
                message,
                f"Thanks for starting a new game! Check the receipt printer, or print the attached [form]({upload_url}). Draw your contribution, then submit by replying to me with the `/submit` command (see `/help` for details).",
            )

        except Exception:
            logger.exception("Failed to upload image")
            bot_handler.send_reply(
                message,
                f"Thanks for starting a new game! Check the receipt printer (had an error uploading a printable form, sorry!). Draw your contribution, then submit by replying to me with the `/submit` command (see `/help` for details).",
            )

        return


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
            attached_image = Image.open(BytesIO(attached_image_bytes))
        except Exception:
            bot_handler.send_reply(message, f"Error: unable to load image; perhaps unrecognized format")
            return

        try:
            parsed_drawing, labels = form_parser.parse_form(
                form_parser.convert_pil_to_opencv(attached_image.convert(mode="L")),
                consts.DRAWING_AREA_PLUS,
                consts.MARKER_MARGIN + consts.BORDER_WIDTH,
            )
        except form_parser.FormParserException as e:
            bot_handler.send_reply(message, f"Error: unable to parse form - please try a different picture; {str(e)}")
            return
        except Exception as e:
            logger.exception("Unknown form parsing error")
            bot_handler.send_reply(message, f"Error: unknown error in parsing form; {str(e)}")
            return

        conn = self._get_connection()
        drawing_db_id = db.convert_drawing_id_from_form_to_db(
            (labels[1], labels[2], labels[3])
        )

        is_submitted = db.get_drawing_is_submitted(conn, drawing_db_id)
        if is_submitted:
            bot_handler.send_reply(message, f"This drawing has already been submitted!")
            return
        
        is_final = db.get_drawing_is_final(conn, drawing_db_id)
        logger.info(f"Is final check: {is_final} for labels {labels} and drawing_db_id {drawing_db_id}")
        if not is_final:
            # Parse out mentioned user id, and get email so we can send a message to them
            mentioned_user_id = zulip_client.parse_mentioned_user_from_message(message)
            if not mentioned_user_id:
                bot_handler.send_reply(message, "Error: please include a tag of the next artist")
                return

            mentioned_user_email = ZULIP_CLIENT.get_email_for_user(mentioned_user_id)
            mentioned_user_name = ZULIP_CLIENT.get_name_for_user(mentioned_user_id)
            if not mentioned_user_email or not mentioned_user_name:
                bot_handler.send_reply(message, f"Error: could not get zulip email and/or name for mentioned user (id: {mentioned_user_id})")
                return


            game_id = db.get_game_id_for_drawing(conn, drawing_db_id)
            next_drawing_id = db.init_drawing(conn, game_id, mentioned_user_id)
            
            db.submit_drawing(
                conn,
                drawing_db_id,
                form_parser.convert_opencv_image_to_jpeg_bytes(parsed_drawing),
            )

            next_drawing_id_for_form = db.convert_drawing_id_from_db_to_form(next_drawing_id)
            is_next_final = db.get_drawing_is_final(conn, next_drawing_id)

            if not is_next_final:
                next_form = image_builder.build_middle_form(
                    next_drawing_id_for_form,
                    mentioned_user_name,
                    parsed_drawing,
                )
            else:
                next_form = image_builder.build_final_form(
                    next_drawing_id_for_form,
                    mentioned_user_name,
                    parsed_drawing,
                )

            img = Image.fromarray(next_form, mode="L")
            RCPRINTER_CLIENT.send_image(img)

            bot_handler.send_reply(
                message,
                "Success! Thanks for submitting. The next artist has been notified...",
            )

            next_user_message = """Hi! You've been chosen to play RC Exquisite Corpse, a collaborative art game. See `/help` to learn how the game works.

Once you're done, reply to me with the `/submit` command, uploading a picture of your form."""

            if not is_next_final:
                next_user_message += " Please also tag the next artist."""

            try:
                upload_url = ZULIP_CLIENT.upload_image(img)
                next_user_message += f"\n\n[form]({upload_url})"
            except Exception:
                logger.exception("Failed to upload image")
                next_user_message += f"\n\n(oops! failed to upload the form)"

            bot_handler.send_message({
                "type": "private",
                "to": mentioned_user_email,
                "subject": "Exquisite Corpse Game",
                "content": next_user_message,
            })
        else:
            db.submit_drawing(
                conn,
                drawing_db_id,
                form_parser.convert_opencv_image_to_jpeg_bytes(parsed_drawing),
            )

            # Also send a message to every other player...
            bot_handler.send_reply(
                message,
                "Success! Thanks for submitting. The game is done and ready to print (use `/print`)!"
            )

        return

    def handle_list(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        sender_id = message.get("sender_id")
        if sender_id is None:
            bot_handler.send_reply(message, "Error: could not get the sender id")
            return
        
        conn = self._get_connection()
        data: list[tuple[int, str, int, int]] = []
        games_for_user = db.get_games_for_user(conn, sender_id)
        for game_id in games_for_user:
            stats = db.get_progress_for_game(conn, game_id)
            if stats is None:
                status = "error (could not get data for game)"
            else:
                n_submitted, n_total = stats
                is_complete = n_submitted == n_total

                if is_complete:
                    status = "completed"
                else:
                    next_artist_id = db.get_next_artist_for_game(conn, game_id)
                    if not next_artist_id:
                        status = "error (could not identify next artist)"
                    elif next_artist_id == sender_id:
                        status = "waiting on you"
                    else:
                        next_artist_name = ZULIP_CLIENT.get_name_for_user(next_artist_id)
                        status = f"waiting on {next_artist_name or next_artist_id}"

            data.append((
                game_id,
                status,
                n_submitted,
                n_total,
            ))

        data = sorted(data, key=lambda x: x[0])

        msg = "\n".join([
            "You are part of the following games [format - {game id}: {status} ({stats})]:",
            *(
                f"- {game_id}: {status} ({n_submitted} of {n_total})"
                for (game_id, status, n_submitted, n_total) in data
            ),
        ])

        bot_handler.send_reply(message, msg)
        return

    def handle_print(self, message: ZulipMessage, bot_handler: AbstractBotHandler) -> None:
        content = message.get("content", "")
        args = content.split()

        if len(args) != 2:
            bot_handler.send_reply(message, "Usage: `/print {game_id}` (use `/list` to see a list of your games, with their ids)")
            return

        sender_id = message["sender_id"]

        sender_name = ZULIP_CLIENT.get_name_for_user(sender_id)
        if sender_name is None:
            bot_handler.send_reply(message, "Error: Could not get name for sender")
            return

        conn = self._get_connection()
        game_id = int(args[1])
        is_complete = db.get_game_is_complete(conn, game_id)

        if is_complete:
            all_drawings_with_ids = db.get_all_drawings_for_game(conn, game_id)
            all_drawings = [x for x, _ in all_drawings_with_ids]
            all_names = [ZULIP_CLIENT.get_name_for_user(x) or "(unknown" for _, x in all_drawings_with_ids]
            form = image_builder.get_completed_game(all_drawings, all_names)
        else:
            next_drawing_data = db.get_next_drawing_for_game(conn, game_id)
            if next_drawing_data["artist_zulip_id"] == sender_id:
                drawing_number = next_drawing_data["drawing_number"]
                lbls_ = db.convert_drawing_id_from_db_to_form(next_drawing_data["id"])

                if drawing_number == 1:
                    form = image_builder.build_start_form(lbls_, sender_name)
                else:
                    is_final = db.get_drawing_is_final(conn, next_drawing_data["id"])
                    prev_drawing_id = db.get_drawing_by_game_id_and_drawing_number(
                        conn,
                        game_id,
                        drawing_number - 1,
                    )

                    prev_im = db.get_submitted_image(conn, prev_drawing_id)

                    if not prev_im:
                        bot_handler.send_reply(message, "Error: Could not build form")
                        return

                    prev_im_as_array = form_parser.convert_pil_to_opencv(prev_im)

                    if not is_final:
                        form = image_builder.build_middle_form(
                            lbls_, sender_name, prev_im_as_array)
                    else:
                        form = image_builder.build_final_form(
                            lbls_, sender_name, prev_im_as_array)
            else:
                bot_handler.send_reply(message, "This game is incomplete, and you are not next, so you may not print this form!")
                return

        img = form_parser.convert_opencv_to_pil(form)
        RCPRINTER_CLIENT.send_image(img)

        try:
            upload_url = ZULIP_CLIENT.upload_image(img)
            bot_handler.send_reply(
                message,
                f"Success! Go check out the printer, or print out your form [here]({upload_url})",
            )
        except Exception:
            logger.exception("Failed to upload image")
            bot_handler.send_reply(
                message,
                f"Success! Go check out the printer (was unable to upload form to Zulip)",
            )

        return

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
