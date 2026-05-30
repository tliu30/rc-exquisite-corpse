import re
import typing as t
from urllib import parse as urlparse

from zulip import Client

ZulipMessage = dict[str, t.Any]

class ZulipClient:

    def __init__(self, config_file):
        self.__client__ = Client(config_file=config_file)
        
    @property
    def __host__(self):
        parts = urlparse.urlsplit(self.__client__.base_url)
        return f"{parts.scheme}://{parts.netloc}"

    def get_email_for_user(self, user_id: int) -> str | None:
        result = self.__client__.get_user_by_id(user_id)

        if not result:
            return None

        user_data = result.get("user")

        if not user_data:
            return None

        email = user_data.get("email")

        if not email:
            return None  # maybe error / complain?

        return email

    def get_image(self, relative_image_url: str) -> bytes | None:
        full_url = f"{self.__host__}/{relative_image_url}"

        if not self.__client__.session:
            return None

        response = self.__client__.session.get(full_url)

        if not response.ok:
            return None

        return response.content


#############################
# Message parsing utilities
#############################

def parse_mentioned_user_from_message(message: ZulipMessage) -> int | None:
    content = message.get("rendered_content")
    
    if not content:
        return None

    results = re.search(r'<span.+data-user-id="(\d+)"', content)

    if not results:
        return None

    return int(results.groups()[0])


def parse_image_url_from_message(message: ZulipMessage) -> str | None:
    content = message.get("rendered_content")

    if not content:
        return None

    results = re.search(r'<img.+data-original-src="([^"]+?)"', content)

    if not results:
        return None

    return results.groups()[0]

