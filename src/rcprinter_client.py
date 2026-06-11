from PIL import Image
import json
import requests

import config
from form_parser import convert_pil_to_jpeg_fobj

class RCPrinterClient:

    def __init__(self, conf_path=config.RCPRINTER_CONF_PATH):
        with open(conf_path, 'r') as f:
            conf = json.load(f)

        self.cookies = conf["cookies"]
        self.csrf_token = conf["cookies"]["receipt_csrf"]
        self.base_url = "https://receipt.recurse.com"

    def send_image(self, image: Image.Image) -> None:
        url = f"{self.base_url}/image"
        fobj = convert_pil_to_jpeg_fobj(image)
        data = fobj.read()

        if len(data) > 65500:
            raise Exception("Image too large; must be under 65500")

        response = requests.post(
            url,
            data=data,
            cookies=self.cookies,
            headers={
                "X-CSRF-TOKEN": self.csrf_token,
                "Content-Type": f"image/jpeg",
            }
        )
        print(f"{response.status_code} - {response.content}")


