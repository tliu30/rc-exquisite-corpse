import json
import requests

CONF_FILE = "/Users/anthonyliu/Projects/receipt-printer-exquisite-corpse/rcprinter.conf.json"

class RCPrinterClient:

    def __init__(self):
        with open(CONF_FILE, 'r') as f:
            conf = json.load(f)

        self.cookies = conf["cookies"]
        self.csrf_token = conf["cookies"]["receipt_csrf"]
        self.base_url = "https://receipt.recurse.com"

    def send_image(self, image_data: bytes, image_format: str = "jpeg") -> None:
        url = f"{self.base_url}/image"

        requests.post(
            url,
            data=image_data,
            cookies=self.cookies,
            headers={
                "X-CSRF-TOKEN": self.csrf_token,
                "Content-Type": f"image/{image_format}",
            }
        )


