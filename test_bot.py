from io import BytesIO

from PIL import Image
from PIL import ImageDraw

from rcprinter_client import RCPrinterClient

class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''

    def usage(self):
        return '''Your description of the bot'''

    def handle_message(self, message, bot_handler):
        content = message.get("content", "")
        new_message = f"hi {content[::-1]}"

        img = Image.new('L', (200, 100), color=(255, ))
        d = ImageDraw.Draw(img)
        d.text((40, 40), content, fill=(0, ))
        d.text((80, 60), new_message, fill=(0, ))

        _c = RCPrinterClient()
        fobj = BytesIO()
        img.save(fobj, format="jpeg")
        fobj.seek(0)
        # _c.send_image(fobj.read())

        bot_handler.send_reply(
            message,
            f"...look at the printer",
        )

handler_class = MyBotHandler

