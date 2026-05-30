import numpy as np
import cv2
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


MAX_WIDTH = 512  # Receipt printer handles images up to 512 pixels wide
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)


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
) -> np.ndarray:
    if drawing_area_size + 2 * border_width + 2 * marker_size > MAX_WIDTH:
        raise ValueError(f"Change dimensions: too big (max width {MAX_WIDTH}px)")

    # Prepend and append white space to add markers to
    im = np.vstack([
        get_white_image((marker_size, MAX_WIDTH)),
        build_drawing_area(),
        get_white_image((marker_size, MAX_WIDTH)),
    ])

    # Margin on the left and right sides of drawing area
    margin_x = (MAX_WIDTH - drawing_area_size - 2 * border_width) / 2
    if margin_x != int(margin_x):
        raise ValueError("Choose dimensions: x dimension must have integer margin")

    margin_x = int(margin_x)

    # Generate and add markers
    top_left_xys = (
        # top left
        (margin_x - marker_size, 0),

        # top right
        (MAX_WIDTH - margin_x, 0),

        # bottom right
        (
            MAX_WIDTH - margin_x,
            marker_size + drawing_area_size + border_width * 2,
        ),

        # bottom left
        (
            margin_x - marker_size,
            marker_size + drawing_area_size + border_width * 2
        ),
    )

    for (id_, (x, y)) in zip(ids, top_left_xys):
        im[y:(y + marker_size), x:(x + marker_size)] = get_marker(id_, marker_size)

    return im


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

