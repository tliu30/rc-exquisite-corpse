from io import BytesIO
import math
import tempfile
import os

import cv2
import numpy as np
from PIL import Image

from image_builder import ARUCO_DICT

class FormParserException(Exception):
    pass
    

def convert_pil_to_opencv(img: Image.Image) -> np.ndarray:
    """To convert from PIL format to opencv, need to reverse color channels"""
    as_array = np.array(img)  # RGB
    if len(as_array.shape) > 2:
        return as_array[:, :, ::-1]  # now, BGR
    else:
        return as_array


def convert_opencv_to_pil(img: np.ndarray) -> Image.Image:
    """To convert from opencv to PIL format, need to reverse color channels"""
    if len(img.shape) > 2:
        return Image.fromarray(img[:, :, ::-1])  # BGR => RGB
    else:
        return Image.fromarray(img)


def convert_pil_to_jpeg_fobj(im: Image.Image) -> BytesIO:
    fobj = BytesIO()
    im.save(fobj, format="jpeg")
    fobj.seek(0)
    return fobj


def convert_opencv_image_to_jpeg_bytes(img: np.ndarray) -> bytes:
    fobj = convert_pil_to_jpeg_fobj(convert_opencv_to_pil(img))
    return fobj.read()


def detect_markers(image: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    parameters =  cv2.aruco.DetectorParameters()
    corners, labels, _ = (
        cv2.aruco.ArucoDetector(ARUCO_DICT, parameters)
        .detectMarkers(image)
    )

    if not corners:
        return []

    return list(zip(labels, corners))


def rotate_image(mat, angle):
    """
    Rotates an image (angle in degrees) and expands image to avoid cropping
    """

    height, width = mat.shape[:2] # Image shape has three dimensions
    image_center = (width/2, height/2) # getRotationMatrix2D needs coordinates in reverse order (width, height) compared to shape

    rotation_mat = cv2.getRotationMatrix2D(image_center, angle, 1.)

    # The rotation calculates the cosine and sine,
    # taking the absolutes of those.
    abs_cos = abs(rotation_mat[0, 0])
    abs_sin = abs(rotation_mat[0, 1])

    # Find the new width and height bounds
    bound_w = int(height * abs_sin + width * abs_cos)
    bound_h = int(height * abs_cos + width * abs_sin)

    # Subtract the old image center (bringing the image
    # back to the origo) and adding the new image
    # center coordinates
    rotation_mat[0, 2] += bound_w/2 - image_center[0]
    rotation_mat[1, 2] += bound_h/2 - image_center[1]

    # Rotate the image with the new bounds and translated rotation matrix
    rotated_mat = cv2.warpAffine(mat, rotation_mat, (bound_w, bound_h))
    return rotated_mat


def fix_rotation_given_marker(image: np.ndarray, corners: np.ndarray):
    # Get unit vector from top left corner of marker to top right
    # The ARUCO detector returns corners in order [tl, tr, br, bl]
    centered = (
        (corners[0, 1, :] - corners[0, 0, :]) *
        np.array([1, -1])  # in images, y increases going down; flip it
    )
    x, y = centered / np.sqrt((centered **2).sum())

    # Calculate angle; if y < 0, reflect angle around axis
    angle_rad = np.arccos(x)
    if y < 0:
        angle_rad = -1 * angle_rad

    correction_deg = -1 * (angle_rad / math.pi * 180)

    return rotate_image(image, correction_deg)



def crop_border(image: np.ndarray) -> np.ndarray:
    by_row = (image == 0).all(axis=1).tolist()
    by_col = (image == 0).all(axis=0).tolist()
    
    # Get first non-black pixel
    x0 = by_row.index(False)
    x1 = len(by_row) - by_row[::-1].index(False)
    y0 = by_col.index(False)
    y1 = len(by_col) - by_col[::-1].index(False)

    return image[x0:x1, y0:y1]


def reorder_markers(markers: list[tuple[np.ndarray, np.ndarray]]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Assuming image is rotated so that it is squared up, ensure corners ordered"""
    # Unpack markers object
    labels, corners = zip(*markers)

    # For each corners array, identify the center points, then identify
    # which points are above the mean vs below the mean
    centers = np.vstack([x[0, :, :].mean(axis=0) for x in corners])
    signs = centers > centers.mean(axis=0)

    keys = [
        f"{'b' if y_above_mean else 't'}{'r' if x_above_mean else 'l'}"
        for x_above_mean, y_above_mean in signs.tolist()
    ]
    argsort = [
        keys.index('tl'),
        keys.index('tr'),
        keys.index('br'),
        keys.index('bl'),
    ]

    sorted_labels = (labels[ix] for ix in argsort)
    sorted_corners = (corners[ix] for ix in argsort)

    return list(zip(sorted_labels, sorted_corners))


def parse_form(image: np.ndarray, transformed_size: int, addl_crop: int = 0) -> tuple[np.ndarray, list[int]]:
    """Can still fail"""
    if len(image.shape) > 2:
        raise Exception("Found a color channel on image; must be grayscale")

    # Get markers, retrying at slightly different rotations if unsuccessful
    markers: list[tuple[np.ndarray, np.ndarray]] = []
    mod_image = image.copy()
    marker_tl_found = False    # for debugging
    any_markers_found = False  # for debugging
    max_num_markers_found = -1 # for debugging
    for rotation_deg in [0, 15, 30, 45, -15, -30, -45]:
        if rotation_deg:
            mod_image = rotate_image(image, rotation_deg)
        markers = detect_markers(mod_image)

        max_num_markers_found = max(len(markers), max_num_markers_found)
        if markers:
            any_markers_found = True
            if any(l == 0 for (l, _) in markers):
                marker_tl_found = True
                break

    # Straighten out image given the top left corner marker (always label 0)
    candidates = [c for (l, c) in markers if l == 0]
    if not candidates:
        msg = "Unable to parse form: "

        if not any_markers_found:
            msg = msg + "no markers found"
        elif not marker_tl_found:
            msg = msg + f"found up to {max_num_markers_found}, but never the top left marker"
        else:
            msg = msg + "found markers, and found top left marker; some other error"

        raise FormParserException(msg)

    label_0_corners = candidates[0]
    mod_image = fix_rotation_given_marker(mod_image, label_0_corners)
    # mod_image = crop_border(mod_image)
    markers = detect_markers(mod_image)

    if len(markers) != 4:
        raise FormParserException(f"Unable to parse form: found {len(markers)}; expected 4")

    # Reorder markers to be (tl, tr, br, bl)
    labels, corners = zip(*reorder_markers(markers))

    # Identify the inner corners of each marker (the drawing's frame)
    # Remember ARUCO detector returns corners in order (tl, tr, br, bl)
    frame_boundaries = np.array([
        corners[0][:, 2],
        corners[1][:, 3],
        corners[2][:, 0],
        corners[3][:, 1],
    ]).squeeze().astype(np.float32)

    # Identify the points we want to transform it to (handles warp & scale)
    tgt_points = np.array([
        [0, 0],
        [transformed_size, 0],
        [transformed_size, transformed_size],
        [0, transformed_size],
    ]).astype(np.float32)

    transformation = cv2.getPerspectiveTransform(
        frame_boundaries.squeeze(),
        tgt_points,
    )

    # Apply all transformations to original image
    if rotation_deg:
        image = rotate_image(image, rotation_deg)
    image = fix_rotation_given_marker(image, label_0_corners)

    transformed_image = cv2.warpPerspective(
        image,
        transformation,
        (transformed_size, transformed_size),
    )

    # Apply the additional crop
    t_h, t_w = transformed_image.shape[:2]
    transformed_image = transformed_image[
        addl_crop:(t_h - addl_crop),
        addl_crop:(t_w - addl_crop),
    ]

    return transformed_image, [x.item() for x in labels]

