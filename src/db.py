import datetime
import math
import sqlite3

def now_timestamp_s():
    return int(datetime.datetime.now().timestamp())

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect("./test.db")


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


def get_next_drawing_number(conn: sqlite3.Connection, game_id: int) -> int:
    res = conn.execute(
        """
        SELECT
            MAX(drawingNumber)
        FROM
            drawing
        WHERE
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
            game.id = drawing.game_id
        WHERE
            drawing.id = ?
        """,
        (drawing_id, ),
    )

    record = res.fetchone()[0]

    if record is None:
        raise Exception("Drawing not found")

    return record[0] == record[1]


def init_drawing(
    conn: sqlite3.Connection,
    game_id: int,
    artist_zulip_id: int,
) -> int:
    next_drawing_number = get_next_drawing_number(conn, game_id)
    
    res = conn.execute(
        """
        INSERT INTO drawing(gameId, drawingNumber, artistZulipId, createdAt) VALUES(?, ?, ?, ?);
        """,
        (game_id, next_drawing_number, artist_zulip_id, now_timestamp_s()),
    )

    if not res.lastrowid:
        raise Exception("Unexpected: no last row id after insert")

    return res.lastrowid


def submit_drawing(
    conn: sqlite3.Connection,
    drawing_id: int,
    image_data: bytes,
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
        (image_data, now_timestamp_s(), drawing_id),
    )


