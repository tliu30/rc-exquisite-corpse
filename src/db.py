from io import BytesIO
import datetime
import math
import sqlite3
from PIL import Image

import form_parser
import config

def now_timestamp_s():
    return int(datetime.datetime.now().timestamp())

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(config.DB_URI)


def setup(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game(
            id INTEGER PRIMARY KEY,
            length INTEGER NOT NULL,
            createdBy INTEGER NOT NULL,
            createdAt INTEGER NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drawing(
            id INTEGER PRIMARY KEY,
            gameId INTEGER NOT NULL,
            drawingNumber INTEGER NOT NULL,
            artistZulipId INTEGER NOT NULL,
            imageData BLOB,
            imageWidth INTEGER,
            imageHeight INTEGER,
            createdAt INTEGER NOT NULL,
            submittedAt INTEGER
        );
    """)


def convert_drawing_id_from_db_to_form(db_id: int) -> tuple[int, int, int]:
    hundreds_place = 0
    tens_place = 0
    ones_place = 0

    if db_id <= (999 - 1):
        ones_place = db_id
    elif db_id <= (999 * 999 - 1):
        tens_place = int(math.floor(db_id / 999))
        ones_place = db_id - tens_place * 999
    elif db_id <= (999 * 999 * 999 - 1):
        hundreds_place = int(math.floor(db_id / (999 * 999)))
        remainder = db_id - hundreds_place * 999 * 999

        tens_place = int(math.floor(remainder / 999))
        remainder = remainder - tens_place * 999

        ones_place = remainder
    else:
        raise ValueError(f"The id {db_id} is too big - we can't make a form from that")

    return (hundreds_place + 1, tens_place + 1, ones_place + 1)


def convert_drawing_id_from_form_to_db(form_id: tuple[int, int, int]) -> int:
    hundreds_place = form_id[0] - 1
    tens_place = form_id[1] - 1
    ones_place = form_id[2] - 1

    return hundreds_place * (999 * 999) + tens_place * 999 + ones_place


def create_game(conn: sqlite3.Connection, created_by: int, length: int = 5) -> int:
    res = conn.execute(
        """
        INSERT INTO game(length, createdBy, createdAt) VALUES(?, ?, ?);
        """,
        (length, created_by, now_timestamp_s()),
    )
    conn.commit()

    if not res.lastrowid:
        raise Exception("Unexpected: there is no last row id after insert")

    return res.lastrowid


def get_drawing(conn: sqlite3.Connection, drawing_id: int):
    res = conn.execute(
        """
        SELECT *
        FROM drawing
        WHERE id = ?;
        """,
        (drawing_id, ),
    )
    return res.fetchone()


def get_drawing_is_submitted(conn: sqlite3.Connection, drawing_id: int):
    res = conn.execute(
        """
        SELECT submittedAt IS NOT NULL
        FROM drawing
        WHERE id = ?;
        """,
        (drawing_id, ),
    )
    record = res.fetchone()
    if record is None:
        return False

    return record[0]


def get_submitted_image(conn: sqlite3.Connection, drawing_id: int) -> Image.Image | None:
    res = conn.execute(
        """
        SELECT imageData
        FROM drawing
        WHERE id = ?;
        """,
        (drawing_id, ),
    )
    row = res.fetchone()

    if row is None:
        return None

    image_bytes = row[0]

    return Image.open(BytesIO(image_bytes))


def get_game_is_complete(conn: sqlite3.Connection, game_id: int):
    res = conn.execute(
        """
        SELECT
            MAX(game.length),
            MAX(drawing.drawingNumber)
        FROM
            game LEFT JOIN
            drawing ON 
            game.id = drawing.gameId
        WHERE
            game.id = ?
        """,
        (game_id, ),
    )

    record = res.fetchone()
    print(f"get game is complete {record}")

    if not record:
        raise Exception(f"Could not get data for game {game_id}")

    return record[0] == record[1]


def get_all_drawings_for_game(conn: sqlite3.Connection, game_id: int) -> list[tuple[Image.Image, int]]:
    res = conn.execute(
        """
        SELECT imageData, artistZulipId
        FROM drawing
        WHERE drawing.gameId = ?;
        """,
        (game_id, ),
    )

    return [
        (Image.open(BytesIO(row[0])), row[1])
        for row in res.fetchall()
    ]

def get_all_participant_ids(conn: sqlite3.Connection, game_id: int) -> set[int]:
    res = conn.execute(
        """
        SELECT DISTINCT artistZulipId
        FROM drawing
        WHERE drawing.gameId = ?
        """,
        (game_id, ),
    )

    return set(x[0] for x in res.fetchall())

def get_game_id_for_drawing(conn: sqlite3.Connection, drawing_id: int) -> int:
    res = conn.execute(
        """
        SELECT gameId
        FROM drawing
        WHERE id = ?;
        """,
        (drawing_id, ),
    )
    return res.fetchone()[0]


def get_games_for_user(conn: sqlite3.Connection, user_id: int):
    res = conn.execute(
        """
        SELECT DISTINCT
            gameId
        FROM
            game
                LEFT JOIN
            drawing
                ON
            game.id = drawing.gameId
        WHERE
            drawing.artistZulipId = ?;
        """,
        (user_id, ),
    )
    return [x[0] for x in res.fetchall()]


def get_progress_for_game(
    conn: sqlite3.Connection,
    game_id: int,
) -> tuple[int, int] | None:
    res = conn.execute(
        """
        SELECT
            SUM(
                CASE WHEN drawing.submittedAt IS NOT NULL
                THEN 1 ELSE 0 END
            ) AS numSubmitted,
            game.length AS numTotal
        FROM
            game
                LEFT JOIN
            drawing
                ON
            game.id = drawing.gameId
        WHERE
            drawing.gameId = ?
        ;
        """,
        (game_id, ),
    )
    return res.fetchone()


def get_next_artist_for_game(
    conn: sqlite3.Connection,
    game_id: int,
) -> int | None:
    res = conn.execute(
        """
        SELECT
            artistZulipid
        FROM
            drawing
        WHERE
            submittedAt IS NULL AND
            gameId = ? 
        ORDER BY id
        """,
        (game_id, ),
    )
    return res.fetchone()[0]


def get_next_drawing_for_game(conn: sqlite3.Connection, game_id: int):
    res = conn.execute(
        """
        SELECT
            id,
            artistZulipId,
            drawingNumber
        FROM drawing
        WHERE
            gameId = ? AND
            submittedAt IS NULL;
        """,
        (game_id, ),
    )

    record = res.fetchone()

    if not record:
        raise Exception("No next artist found")

    return { "id": record[0], "artist_zulip_id": record[1], "drawing_number": record[2]}


def get_drawing_by_game_id_and_drawing_number(conn: sqlite3.Connection, game_id: int, drawing_number: int):
    res = conn.execute(
        """
        SELECT *
        FROM drawing
        WHERE gameId = ? AND drawingNumber = ?;
        """,
        (game_id, drawing_number),
    )
    record = res.fetchone()

    if not record:
        raise Exception("No drawing found")

    return record[0]


def get_next_drawing_number(conn: sqlite3.Connection, game_id: int) -> int:
    res = conn.execute(
        """
        SELECT
            MAX(drawingNumber)
        FROM
            drawing
        WHERE
            submittedAt IS NULL AND
            gameId = ?;
        """,
        (game_id, ),
    )

    last_number = res.fetchone()[0]

    if last_number is None:
        return 1
    
    return last_number + 1


def get_drawing_is_final(conn: sqlite3.Connection, drawing_id: int):
    res = conn.execute(
        """
        SELECT
            game.length AS gameLength,
            drawing.drawingNumber AS drawingNumber
        FROM
            game
                LEFT JOIN
            drawing
                ON
            game.id = drawing.gameId
        WHERE
            drawing.id = ?
        """,
        (drawing_id, ),
    )

    record = res.fetchone()

    if record is None:
        raise Exception("Drawing not found")

    return record[0] <= record[1]


def init_drawing(
    conn: sqlite3.Connection,
    game_id: int,
    artist_zulip_id: int,
) -> int:
    next_drawing_number = get_next_drawing_number(conn, game_id)

    existing_drawing_id = None
    try:
        record = get_drawing_by_game_id_and_drawing_number(conn, game_id, next_drawing_number)
        existing_drawing_id = record[0]
    except Exception:
        pass

    if existing_drawing_id:
        return existing_drawing_id
    
    res = conn.execute(
        """
        INSERT INTO drawing(gameId, drawingNumber, artistZulipId, createdAt) VALUES(?, ?, ?, ?);
        """,
        (game_id, next_drawing_number, artist_zulip_id, now_timestamp_s()),
    )
    conn.commit()

    if not res.lastrowid:
        raise Exception("Unexpected: no last row id after insert")

    return res.lastrowid


def submit_drawing(
    conn: sqlite3.Connection,
    drawing_id: int,
    image_bytes: bytes,
) -> None:
    conn.execute(
        """
        UPDATE
            drawing
        SET
            imageData = ?,
            submittedAt = ?
        WHERE
            id = ?;
        """,
        (image_bytes, now_timestamp_s(), drawing_id),
    )
    conn.commit()


