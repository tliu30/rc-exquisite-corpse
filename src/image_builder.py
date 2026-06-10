from io import BytesIO
import numpy as np
import cv2
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


MAX_WIDTH = 512  # Receipt printer handles images up to 512 pixels wide
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)
PATH_TO_FONT = "/Library/Fonts/Arial Unicode.ttf"


def get_white_image(size: tuple[int, int]) -> np.ndarray:
    return np.ones(
        size,
        dtype=np.uint8,  # this dtype is compatible with grayscale images
    ) * 255              # make it white


def get_marker(i: int, size: int) -> np.ndarray:
    if i < 0 or i > 999:
        raise Exception("Out of bounds i; choose between 0-999")
        
    return cv2.aruco.generateImageMarker(ARUCO_DICT, i, size)


def crop_and_center(im: np.ndarray) -> np.ndarray:
    """Only for black and white image arrays; assumed grayscale"""
    black_mask = (im == 0)

    def first_black_pixel(mask: np.ndarray, axis: int) -> int:
        ixes = mask.argmax(axis=axis)
        return ixes[ixes > 0].min()

    margins = (
        first_black_pixel(black_mask, 1), # left
        first_black_pixel(black_mask[:, ::-1], 1),  # right
        first_black_pixel(black_mask, 0),  # top
        first_black_pixel(black_mask[::-1, :], 0),  # bottom
    )

    cropped_im = im[
        margins[2]:(im.shape[0] - margins[3]),
        margins[0]:(im.shape[1] - margins[1]),
    ]

    new_margin_x = (MAX_WIDTH - cropped_im.shape[1]) / 2
    new_margin_left = int(np.floor(new_margin_x))
    new_margin_right = int(np.ceil(new_margin_x))

    return np.hstack([
        get_white_image((cropped_im.shape[0], new_margin_left)),
        cropped_im,
        get_white_image((cropped_im.shape[0], new_margin_right)),
    ])


def build_drawing_area(
    drawing_area_size: int = 400,
    border_width: int = 3,
) -> np.ndarray:
    """Note: drawing area is square"""
    if drawing_area_size + 2 * border_width > MAX_WIDTH:
        raise ValueError(f"Change dimensions: too big (max width {MAX_WIDTH}px)")

    # Compute total dimensions
    #
    # Includes automatic margins on X-dimension
    # No margins on Y-dimension
    width = MAX_WIDTH
    height = drawing_area_size + 2 * border_width

    im = get_white_image((height, width))

    # Margin on the left and right sides
    margin_x = (width - drawing_area_size - 2 * border_width) / 2
    if margin_x != int(margin_x):
        raise ValueError("Choose dimensions: x dimension must have integer margin")

    margin_x = int(margin_x)

    # Draw the borders in black
    min_x = margin_x
    max_x = width - margin_x

    im[:border_width, min_x:max_x] = 0
    im[border_width:(-1 * border_width), min_x:(min_x + 3)] = 0
    im[border_width:(-1 * border_width), (max_x - 3):max_x] = 0
    im[(-1 * border_width):, min_x:max_x] = 0

    return im


def build_drawing_area_with_aruco_markers(
    ids: tuple[int, int, int, int],
    drawing_area_size: int = 400,
    border_width: int = 3,
    marker_size: int = 48,
    addl_left: np.ndarray | None = None,
    addl_top: np.ndarray | None = None,
    addl_bottom: np.ndarray | None = None,
) -> np.ndarray:
    MARKER_MARGIN = 4

    if drawing_area_size + 2 * border_width + 2 * marker_size > MAX_WIDTH:
        raise ValueError(f"Change dimensions: too big (max width {MAX_WIDTH}px)")

    # Prepend and append white space to add markers to
    im = np.vstack([
        get_white_image((marker_size + MARKER_MARGIN, MAX_WIDTH)),
        build_drawing_area(drawing_area_size=drawing_area_size, border_width=border_width),
        get_white_image((marker_size + MARKER_MARGIN, MAX_WIDTH)),
    ])

    # Margin on the left and right sides of drawing area
    margin_x = (MAX_WIDTH - drawing_area_size - 2 * border_width - 2 * MARKER_MARGIN) / 2
    if margin_x != int(margin_x):
        raise ValueError("Choose dimensions: x dimension must have integer margin")

    margin_x = int(margin_x)

    # Generate and add markers
    height = im.shape[0]
    top_left_xys = (
        # top left
        (margin_x - marker_size, 0),

        # top right
        (MAX_WIDTH - margin_x, 0),

        # bottom right
        (
            MAX_WIDTH - margin_x,
            height - marker_size,
        ),

        # bottom left
        (
            margin_x - marker_size,
            height - marker_size,
            # marker_size + drawing_area_size + border_width * 2
        ),
    )

    for (id_, (x, y)) in zip(ids, top_left_xys):
        im[y:(y + marker_size), x:(x + marker_size)] = get_marker(id_, marker_size)

    # Add additional images (img, top, left, bottom, right)
    # Place each next to the corresponding border
    full_height, _ = im.shape

    if addl_left is not None:
        cur_h, cur_w = addl_left.shape
        top = marker_size + MARKER_MARGIN + border_width
        right = margin_x
        bottom = top + cur_h
        left = right - cur_w
        
        im[top:bottom, left:right] = addl_left

    if addl_top is not None:
        cur_h, cur_w = addl_top.shape
        bottom = marker_size + MARKER_MARGIN
        left = margin_x + MARKER_MARGIN + border_width
        top = bottom - cur_h
        right = left + cur_w
        
        im[top:bottom, left:right] = addl_top

    if addl_bottom is not None:
        cur_h, cur_w = addl_bottom.shape
        top = full_height - marker_size - MARKER_MARGIN
        left = margin_x + MARKER_MARGIN + border_width

        bottom = top + cur_h
        right = left + cur_w
        
        im[top:bottom, left:right] = addl_bottom

    return im


def get_text(text: str, path_to_font_ttf: str, font_size: int, canvas_size: tuple[int, int], start: tuple[int, int]) -> np.ndarray:
    canvas = Image.fromarray(get_white_image(canvas_size))

    im_draw = ImageDraw.Draw(canvas)
    im_draw.text(
        start,
        text,
        font=ImageFont.truetype(path_to_font_ttf, font_size),
        fill=(0,)
    )

    return np.array(canvas)


def build_title(text: str, path_to_font_ttf: str, font_size: int) -> np.ndarray:
    canvas = Image.fromarray(get_white_image((512, 512)))

    im_draw = ImageDraw.Draw(canvas)
    im_draw.text(
        (0, 0),
        text,
        font=ImageFont.truetype(path_to_font_ttf, font_size),
        fill=(0,)
    )

    im = np.array(canvas)

    return crop_and_center(im)


def build_titled_card(text: str, path_to_font_ttf: str, ids: tuple[int,int,int]) -> np.ndarray:
    # "/System/Library/Fonts/Supplemental/Arial.ttf",
    title = build_title(text, path_to_font_ttf, 90)
    drawing_card = build_drawing_area_with_aruco_markers(
        (0, ids[0], ids[1], ids[2]),
        drawing_area_size=200,
        marker_size=144,
    )

    full_img = np.vstack([
        title,
        get_white_image((20, MAX_WIDTH)),
        drawing_card,
    ])

    return full_img

def get_completed_game(images: list[bytes]) -> np.ndarray:
    return np.vstack([
        np.array(
            Image
            .frombytes("RGB", (512, 512), x)
            .resize((256, 256))
        ) for x in images
    ] * 3)


import os
PROJECT_ROOT = "/Users/anthonyliu/Projects/receipt-printer-exquisite-corpse/"


def load_title() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/title.jpeg")
    return np.array(Image.open(path).convert(mode="L"))


def load_draw_here() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/draw-instructions.jpeg")
    return np.array(Image.open(path).convert(mode="L"))


def load_prev_label() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/prev-drawing.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_youre_the_first() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/first.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_bottom_reminder() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/bottom.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_final_notice() -> np.ndarray:
    path = os.path.join(PROJECT_ROOT, "./src/assets/final.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def build_start_form(ids: tuple[int, int, int], name: str):
    return np.vstack([
        load_title(),
        np.zeros((1, 512), dtype=np.uint8),
        get_text(f"For {name}", PATH_TO_FONT, 30, (60, 512), (10, 5)),
        np.zeros((1, 512), dtype=np.uint8),
        get_white_image((20, 512)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
            drawing_area_size=200,
            marker_size=144,
            addl_left=load_draw_here(),
            addl_top=load_youre_the_first(),
            addl_bottom=load_bottom_reminder(),
        ),
    ])


def build_middle_form(ids: tuple[int, int, int], name: str, prev_image: np.ndarray):
    return np.vstack([
        load_title(),
        np.zeros((1, 512), dtype=np.uint8),
        get_text(f"For {name}", PATH_TO_FONT, 30, (60, 512), (10, 5)),
        np.zeros((1, 512), dtype=np.uint8),
        get_white_image((20, 512)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
            drawing_area_size=200,
            marker_size=144,
            addl_left=load_draw_here(),
            addl_top=np.vstack([
                load_prev_label(),
                prev_image[-10:, :],
            ]),
            addl_bottom=load_bottom_reminder(),
        ),
    ])

def build_final_form(ids: tuple[int, int, int], name: str, prev_image: np.ndarray):
    return np.vstack([
        load_title(),
        np.zeros((1, 512), dtype=np.uint8),
        get_text(f"For {name}", PATH_TO_FONT, 30, (60, 512), (10, 5)),
        np.zeros((1, 512), dtype=np.uint8),
        get_white_image((20, 512)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
            drawing_area_size=200,
            marker_size=144,
            addl_left=load_draw_here(),
            addl_top=np.vstack([
                load_prev_label(),
                prev_image[-10:, :],
            ]),
            addl_bottom=load_final_notice(),
        ),
    ])
