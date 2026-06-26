import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from PIL import Image
import json
import requests
import time

import config
from form_parser import convert_pil_to_jpeg_fobj


def load_key(key_as_str: str) -> ed25519.Ed25519PrivateKey:
    key = load_pem_private_key(key_as_str.encode(), password=None)

    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key must be of type ed25519")

    return key


def get_signature(private_key: ed25519.Ed25519PrivateKey, content: bytes) -> str:
    as_bytes = private_key.sign(content)
    return base64.b64encode(as_bytes).decode('ascii')


class RCPrinterClient:

    def __init__(self):
        self.private_key = load_key(config.RCPRINTER_PRIVATE_KEY)
        self.base_url = "https://receipt.recurse.com"

    def send_image(self, image: Image.Image) -> None:

        def _get_data(img: Image.Image) -> bytes:
            return convert_pil_to_jpeg_fobj(img).read()
        
        def _send(data: bytes, cut: bool) -> None:
            url = f"{self.base_url}/image?cut={1 if cut else 0}"
            signature = get_signature(self.private_key, data)
            response = requests.post(
                url,
                data=data,
                headers={
                    "Signature": signature,
                    "Content-Type": f"image/jpeg",
                }
            )
            print(f"rcprinter response: {response.status_code} - {response.content}")

        # Data has to be smaller than 65536 per send
        w, h = image.size
        total_size = len(_get_data(image))
        step_size = int((40000 / total_size) * h)

        cur = 0
        while cur < h:
            next = min(cur + step_size, h)
            cropped = image.crop(box=(0, cur, w, next))
            _send(_get_data(cropped), next >= h)
            time.sleep(1)  # wait; give time to print
            cur = next

