from PIL import Image
import json
import requests
import time

import config
from form_parser import convert_pil_to_jpeg_fobj

class RCPrinterClient:

    def __init__(self):
        self.cookies = {
            "receipt_csrf": config.RCPRINTER_CSRF,
            "session": config.RCPRINTER_SESSION,
            "session.sig": config.RCPRINTER_SESSION_SIG,
        }
        self.csrf_token = config.RCPRINTER_CSRF
        self.base_url = "https://receipt.recurse.com"

    def send_image(self, image: Image.Image) -> None:

        def _get_data(img: Image.Image) -> bytes:
            return convert_pil_to_jpeg_fobj(img).read()
        
        def _send(data: bytes, cut: bool) -> None:
            url = f"{self.base_url}/image?cut={1 if cut else 0}"
            response = requests.post(
                url,
                data=data,
                cookies=self.cookies,
                headers={
                    "X-CSRF-TOKEN": self.csrf_token,
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

