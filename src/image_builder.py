import os
from io import BytesIO
import numpy as np
import cv2
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import consts
import config

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


def build_drawing_area(
    drawing_area_size: int,
    border_width: int,
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
    drawing_area_size: int = consts.DRAWING_AREA,
    border_width: int = consts.BORDER_WIDTH,
    marker_size: int = consts.MARKER_SIZE,
    marker_margin: int = consts.MARKER_MARGIN,
    addl_left: np.ndarray | None = None,
    addl_top: np.ndarray | None = None,
    addl_bottom: np.ndarray | None = None,
) -> np.ndarray:
    if drawing_area_size + 2 * border_width + 2 * marker_size > MAX_WIDTH:
        raise ValueError(f"Change dimensions: too big (max width {MAX_WIDTH}px)")

    # Prepend and append white space to add markers to
    im = np.vstack([
        get_white_image((marker_size + marker_margin, MAX_WIDTH)),
        build_drawing_area(drawing_area_size, border_width),
        get_white_image((marker_size + marker_margin, MAX_WIDTH)),
    ])

    # Margin on the left and right sides of drawing area
    margin_x = (MAX_WIDTH - drawing_area_size - 2 * border_width - 2 * marker_margin) / 2
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
        top = marker_size + marker_margin + border_width
        right = margin_x
        bottom = top + cur_h
        left = right - cur_w
        
        im[top:bottom, left:right] = addl_left

    if addl_top is not None:
        cur_h, cur_w = addl_top.shape
        bottom = marker_size + marker_margin
        left = margin_x + marker_margin + border_width
        top = bottom - cur_h
        right = left + cur_w
        
        im[top:bottom, left:right] = addl_top

    if addl_bottom is not None:
        cur_h, cur_w = addl_bottom.shape
        top = full_height - marker_size - marker_margin
        left = margin_x + marker_margin + border_width

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


def load_title() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/title.jpeg")
    return np.array(Image.open(path).convert(mode="L"))


def load_draw_here() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/draw-instructions.jpeg")
    return np.array(Image.open(path).convert(mode="L"))


def load_prev_label() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/prev-drawing.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_youre_the_first() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/first.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_bottom_reminder() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/bottom.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def load_final_notice() -> np.ndarray:
    path = os.path.join(config.PROJECT_ROOT, "./src/assets/final.jpeg")
    return np.array(Image.open(path).convert(mode="L"))

def build_start_form(ids: tuple[int, int, int], name: str):
    return np.vstack([
        load_title(),
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_text(f"For {name}", config.FONT_PATH, 30, (60, MAX_WIDTH), (10, 5)),
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_white_image((20, MAX_WIDTH)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
            addl_left=load_draw_here(),
            addl_top=load_youre_the_first(),
            addl_bottom=load_bottom_reminder(),
        ),
    ])


def build_middle_form(ids: tuple[int, int, int], name: str, prev_image: np.ndarray):
    return np.vstack([
        load_title(),
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_text(f"For {name}", config.FONT_PATH, 30, (60, MAX_WIDTH), (10, 5)),
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_white_image((20, MAX_WIDTH)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
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
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_text(f"For {name}", config.FONT_PATH, 30, (60, MAX_WIDTH), (10, 5)),
        np.zeros((1, MAX_WIDTH), dtype=np.uint8),
        get_white_image((20, MAX_WIDTH)),
        build_drawing_area_with_aruco_markers(
            (0, ids[0], ids[1], ids[2]),
            addl_left=load_draw_here(),
            addl_top=np.vstack([
                load_prev_label(),
                prev_image[-10:, :],
            ]),
            addl_bottom=load_final_notice(),
        ),
    ])



def get_annotated_image(im: np.ndarray, annotation: str) -> np.ndarray:
    # Assumes grayscale
    im_h, _ = im.shape[:2]

    text_array = get_text(annotation, config.FONT_PATH, 28, (50, 1000), (0, 0))
    text_h, text_w = text_array.shape[:2]

    is_black = text_array < 255
    
    x_0 = is_black.max(axis=0).tolist().index(True)
    x_1 = text_w - is_black.max(axis=0)[::-1].tolist().index(True) 

    if x_1 - x_0 < im_h:
        x_1 = x_0 + im_h 
    
    cropped_text_array = text_array[
        :,
        np.clip(x_0 - 20, 0, text_w):np.clip(x_1 + 20, 0, text_w),
    ]


    cropped_text = (
        Image.fromarray(cropped_text_array)
        .transpose(Image.Transpose.ROTATE_270)
        .resize((text_h, im_h))
    )

    return np.hstack([im, np.array(cropped_text)])


def get_completed_game(
    images: list[Image.Image],
    annotations: list[str],
) -> np.ndarray:
    if not images:
        return np.array([])

    annotated_images = []
    for image, annotation in zip(images, annotations):
        image_array = np.array(image.resize((450, 450)))
        annotated_image = get_annotated_image(image_array, annotation)
        annotated_images.append(annotated_image)

    section_width = annotated_images[0].shape[1]

    title = load_title()
    title_h, title_w = title.shape
    ratio = section_width / title_w
    new_h = int(title_h * ratio)
    new_w = int(title_w * ratio)
    resized_title = np.array(Image.fromarray(load_title()).resize((new_w, new_h)))

    return np.vstack([
        resized_title,
        get_white_image((20, section_width)),
        *annotated_images,
    ])


