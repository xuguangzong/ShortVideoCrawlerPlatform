import asyncio
import sys
import aioredis
import random
from asyncio import Task
import matplotlib.pyplot as plt
from typing import Optional, List, Dict

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_result
from playwright.async_api import Page
from playwright.async_api import Cookie
from playwright.async_api import BrowserContext
from playwright.async_api import async_playwright

from base_spider import Spider
from media_platform.xhs.client import XHSClient
from config import xhs_url, redis_db_host, redis_db_pwd
from exception import DataFetchError
from models.xhs.m_xhs import update_xhs_note_comment, update_xhs_note
from utils import get_user_agent, get_login_qrcode, convert_cookies, show_qrcode

"""
Playwright是微软开源的一个UI自动化测试工具。添加了默认等待时间增加脚本稳定性，并提供视频录制、网络请求支持、自定义的定位器、自带调试器等新特性
Playwright是一个用于自动化Web浏览器测试和Web数据抓取的开源库。它由Microsoft开发，支持Chrome、Firefox、Safari、Edge和WebKit浏览器。
Playwright的一个主要特点是它能够在所有主要的操作系统（包括Windows、Linux和macOS）上运行，并且它提供了一些强大的功能，如跨浏览器测试、
支持无头浏览器、并行执行测试、元素截图和模拟输入等。它主要有以下优势：
兼容多个浏览器，而且所有浏览器都使用相同的API。
速度快、稳定性高，即使在大型、复杂的Web应用程序中也可以运行。
支持无头浏览器，因此可以在没有可见界面的情况下运行测试，从而提高测试效率。
提供了丰富的 API，以便于执行各种操作，如截图、模拟输入、拦截网络请求等。

需要  python 3.7版本以上
"""


class XiaoHongShuSpider(Spider):
    def __init__(self):
        self.login_phone = None
        self.login_type = None
        self.keywords = None
        self.web_session = None
        self.cookies: Optional[List[Cookie]] = None
        self.browser_context: Optional[BrowserContext] = None
        self.context_page: Optional[Page] = None
        self.proxy: Optional[Dict] = None
        self.user_agent = get_user_agent()
        self.xhs_client: Optional[XHSClient] = None
        self.index_url = xhs_url[0]

    def init_spider(self, **kwargs):
        for key in kwargs.keys():
            setattr(self, key, kwargs[key])

    async def update_cookies(self):
        """
        设置cookies  保持登录
        :return:
        """
        self.cookies = await self.browser_context.cookies()

    async def start_spider(self):
        async with async_playwright() as playwright:
            # 启动浏览器 并创建单个浏览器上下文
            chromium = playwright.chromium
            # 创建谷歌浏览器 ，开启启动无头模式
            browser = await chromium.launch(headless=True)
            # new_content 方法其实是为了创建一个独立的全新上下文环境，它的目的是为了防止多个测试用例并行时各个用例间不受干扰
            self.browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent,
                proxy=self.proxy
            )
            # 执行JS 绕过反自动化及爬虫检测
            await self.browser_context.add_init_script(path="libs/stealth.min.js")
            # 新建选项卡
            self.context_page = await self.browser_context.new_page()
            # 进行url请求
            await self.context_page.goto(self.index_url)

            # 扫描二维码登录
            await self.login()
            await self.update_cookies()

            # # 初始化请求客户端
            cookie_str, cookie_dict = convert_cookies(self.cookies)
            self.xhs_client = XHSClient(
                proxies=self.proxy,
                headers={
                    "User-Agent": self.user_agent,
                    "Cookie": cookie_str,
                    "Origin": self.index_url,
                    "Referer": self.index_url,
                    "Content-Type": "application/json;charset=UTF-8"
                },
                playwright_page=self.context_page,
                cookie_dict=cookie_dict,

            )

            # 搜索笔记并检索它们的评论信息。
            await self.search_posts()

            # 阻塞主爬虫协同程序
            await asyncio.Event().wait()

    async def login(self):
        """
        登录小红书网站并保持 webdriver 登录状态
        :return:
        """
        if self.login_type == "qrcode":
            # 二维码登录
            await self.login_by_qrcode()
        elif self.login_type == "phone":
            # 手机验证码登录
            await self.login_by_mobile()
        elif self.login_type == "handby":
            # 使用预设置的cookie登录
            await self.browser_context.add_cookies([{
                'name': 'web_session',
                'value': self.web_session,
                'domain': ".xiaohongshu.com",
                'path': "/"
            }])
        else:
            pass

    async def login_by_qrcode(self):
        """
        二维码登录
        :return:
        """
        print("开始扫描二维码，登录小红书")

        # 1、找到登录的二维码
        base64_qrcode_img = await get_login_qrcode(
            self.context_page, selector="div.login-container > div.left > div.qrcode > img"
        )
        if not base64_qrcode_img:
            # TODO 如果本网站没有自动弹出登录对话框，我们将手动点击登录按钮
            print("登录失败，没有找到qrcode，请检查。")
            sys.exit()
        # 获取未登录会话
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = convert_cookies(current_cookie)
        no_logged_in_session = cookie_dict.get("web_session")
        # 显示登录二维码
        new_img = show_qrcode(base64_qrcode_img)

        plt.figure(figsize=(8, 8))
        plt.ion()  # 打开交互模式
        plt.axis('off')  # 不需要坐标轴
        plt.imshow(new_img)
        plt.pause(30)  # 该句显示图片30秒
        plt.ioff()  # 显示完后一定要配合使用plt.ioff()关闭交互模式，否则可能出奇怪的问题
        plt.clf()  # 清空图片
        plt.close()  # 清空窗口
        login_flag: bool = await self.check_login_state(no_logged_in_session)
        if not login_flag:
            print("登录失败  ，请重试")
            sys.exit()
        wait_redirect_seconds = 5
        print(f"登录成功，等待 {wait_redirect_seconds} 秒后，进行重定向 ...")
        await asyncio.sleep(wait_redirect_seconds)

    @retry(stop=stop_after_attempt(30), wait=wait_fixed(1), retry=retry_if_result(lambda value: value is False))
    async def check_login_state(self, no_logged_in_session: str) -> bool:
        """
        检查当前登录状态是否成功，返回True，否则返回False
        :param self:
        :param no_logged_in_session:
        :return:
        """
        # 如果登录不成功，将抛出重试异常
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = convert_cookies(current_cookie)
        current_web_session = cookie_dict.get("web_session")
        if current_web_session != no_logged_in_session:
            return True
        return False

    async def login_by_mobile(self):
        print("开始在小红书上执行手机号+验证码登录")
        login_container_ele = await self.context_page.wait_for_selector("div.login-container")
        # 填写登录电话
        input_ele = await login_container_ele.query_selector("label.phone > input")
        await input_ele.fill(self.login_phone)
        await asyncio.sleep(0.5)

        # 点击发送验证码，从redis服务器填写验证码。
        send_btn_ele = await login_container_ele.query_selector("label.auth-code > span")
        await send_btn_ele.click()
        sms_code_input_ele = await login_container_ele.query_selector("label.auth-code > input")
        submit_btn_ele = await login_container_ele.query_selector("div.input-container > button")
        redis_obj = aioredis.from_url(url=redis_db_host, password=redis_db_pwd, decode_responses=True)
        max_get_sms_code_time = 60 * 2
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = convert_cookies(current_cookie)
        no_logged_in_session = cookie_dict.get("web_session")
        while max_get_sms_code_time > 0:
            print(f"从redis剩余时间获取短信代码{max_get_sms_code_time}s ...")
            await asyncio.sleep(1)
            sms_code_key = f"xhs_{self.login_phone}"
            sms_code_value = await redis_obj.get(sms_code_key)
            if not sms_code_value:
                max_get_sms_code_time -= 1
                continue

            await sms_code_input_ele.fill(value=sms_code_value)  # 输入短信验证码

            await asyncio.sleep(0.5)
            agree_privacy_ele = self.context_page.locator("xpath=//div[@class='agreements']//*[local-name()='svg']")
            await agree_privacy_ele.click()  # 点击“同意”隐私政策
            await asyncio.sleep(0.5)
            await submit_btn_ele.click()  # 点击登录按钮
            # TODO
            # 有必要检查验证码的正确性，因为可能输入的验证码不正确。
            break
        login_flag: bool = await self.check_login_state(no_logged_in_session)
        if not login_flag:
            print("登录失败，请确认短信码")
            sys.exit()
        wait_redirect_seconds = 5
        print(f"登录成功后等待{wait_redirect_seconds} 秒后  重定向 ...")
        await asyncio.sleep(wait_redirect_seconds)

    async def search_posts(self):
        print("开始搜索小红书关键词")
        # 可以修改源代码以允许传递一批关键字
        for keyword in [self.keywords]:
            note_list: List[str] = []
            max_note_len = 2
            page = 1
            while max_note_len > 0:
                # 根据关键字获取多个笔记
                posts_res = await self.xhs_client.get_note_by_keyword(
                    keyword=keyword,
                    page=page,
                )
                page += 1
                for post_item in posts_res.get("items"):
                    max_note_len -= 1
                    # 获取每一个笔记的  id
                    note_id = post_item.get("id")
                    try:
                        # 根据笔记id 获取笔记详情
                        note_detail = await self.xhs_client.get_note_by_id(note_id)
                    except DataFetchError as ex:
                        print(ex)
                        continue
                    await update_xhs_note(note_detail)
                    await asyncio.sleep(1)
                    note_list.append(note_id)
            print(f"keyword:{keyword}, note_list:{note_list}")
            # 开始发送评论
            await self.send_comment(note_list)
            # 获取笔记的评论
            await self.batch_get_note_comments(note_list)

    async def batch_get_note_comments(self, note_list: List[str]):
        task_list: List[Task] = []
        for note_id in note_list:
            task = asyncio.create_task(self.get_comments(note_id), name=note_id)
            task_list.append(task)
        await asyncio.wait(task_list)

    async def get_comments(self, note_id: str):
        print(f"开始获取{note_id} 内容 ")
        all_comments = await self.xhs_client.get_note_all_comments(note_id=note_id, crawl_interval=random.random())
        for comment in all_comments:
            await update_xhs_note_comment(note_id=note_id, comment_item=comment)

    async def send_comment(self, note_list: List[str]):
        """
        发送评论
        :param note_list:
        :return:
        """
        for note_id in note_list:
            print(f"开始发送{note_id} 评论内容 ")
            res_comment = await self.xhs_client.send_comment(note_id=note_id, content="真不错!!")
            print(f"评论成功------{res_comment}")
            await asyncio.sleep(3)
