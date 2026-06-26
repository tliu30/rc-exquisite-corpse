#! /usr/bin/env python
import argparse

from PIL import Image

import config
import db
import image_builder
import form_parser
import rcprinter_client
import zulip_client

conn = db.get_connection()
zc = zulip_client.ZulipClient(config.ZULIP_CONF_PATH)
rc = rcprinter_client.RCPrinterClient(config.RCPRINTER_CONF_PATH)

parser = argparse.ArgumentParser()
parser.add_argument("game", type=int)
parser.add_argument("drawing_number", type=int)

args = parser.parse_args()

drawing_id = db.get_drawing_by_game_id_and_drawing_number(
    conn,
    args.game,
    args.drawing_number,
)
artist_zulip_id = db.get_artist_id_for_drawing(conn, drawing_id)
artist_zulip_name = zc.get_name_for_user(artist_zulip_id)

is_final = db.get_drawing_is_final(conn, drawing_id)

if not artist_zulip_name:
    raise Exception(f"No artist name found for id {artist_zulip_id}")

lbls = db.convert_drawing_id_from_db_to_form(drawing_id)

image: Image.Image
if args.drawing_number == 1:
    image = image_builder.build_start_form(lbls, artist_zulip_name)
elif not is_final:
    prev_image = db.get_image_data_by_game_id_and_drawing_number(
        conn,
        args.game, 
        args.drawing_number - 1,
    )
    image = image_builder.build_middle_form(
        lbls,
        artist_zulip_name,
        form_parser.convert_pil_to_opencv(prev_image),
    )
else:
    prev_image = db.get_image_data_by_game_id_and_drawing_number(
        conn,
        args.game, 
        args.drawing_number - 1,
    )
    first_image = db.get_image_data_by_game_id_and_drawing_number(
        conn,
        args.game, 
        1,
    )
    image = image_builder.build_final_form(
        lbls,
        artist_zulip_name,
        form_parser.convert_pil_to_opencv(prev_image),
        form_parser.convert_pil_to_opencv(first_image),
    )

rc.send_image(form_parser.convert_opencv_to_pil(image))

