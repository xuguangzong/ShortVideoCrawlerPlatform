import re
import time
import base64
import random
from io import BytesIO
from PIL import Image, ImageDraw
from typing import Optional, List, Tuple, Dict
from playwright.async_api import Page
from playwright.async_api import Cookie


def get_user_agent() -> str:
    user_agent = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.79 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36"
    ]

    return random.choice(user_agent)


async def get_login_qrcode(page: Page, selector: str) -> str:
    """
    从目标选择其中找到登录二维码
    :param page:
    :param selector:
    :return:
    """
    try:
        elements = await page.wait_for_selector(
            selector=selector
        )
        login_qrcode_img = await elements.get_property("src")
        return str(login_qrcode_img)
    except Exception as e:
        print(e)
        return ""


def convert_cookies(cookies: Optional[List[Cookie]]) -> Tuple[str, Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join([f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies])
    cookie_dict = dict()
    for cookie in cookies:
        cookie_dict[cookie.get('name')] = cookie.get('value')
    return cookies_str, cookie_dict


def show_qrcode(qr_code: str):
    """
    解析base64编码qrcode图像并显示它
    :param qr_code:
    :return:
    """
    qr_code = qr_code.split(",")[1]
    qr_code = base64.b64decode(qr_code)
    image = Image.open(BytesIO(qr_code))

    # 在二维码周围添加方形边框，显示在边框内，提高扫描精度.
    width, height = image.size
    new_image = Image.new('RGB', (width + 20, height + 20), color=(255, 255, 255))
    new_image.paste(image, (10, 10))
    draw = ImageDraw.Draw(new_image)
    draw.rectangle((0, 0, width + 19, height + 19), outline=(0, 0, 0), width=1)
    # new_image.show()
    # time.sleep(3)
    # image.close()
    return new_image


def get_current_timestamp():
    return int(time.time() * 1000)


def match_interact_info_count(count_str: str) -> int:
    if not count_str:
        return 0

    match = re.search(r'\d+', count_str)
    if match:
        number = match.group()
        return int(number)
    else:
        return 0
