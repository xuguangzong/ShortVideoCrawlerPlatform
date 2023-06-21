import asyncio
import argparse
import sys

import config
from media_platform.xhs.spider import XiaoHongShuSpider


class CrawlerFactory:
    @staticmethod
    def get_crawler(platform: str):
        if platform == "xhs":
            return XiaoHongShuSpider()
        elif platform == "dy":
            pass
        else:
            raise ValueError("invalid short video platform  currently only supported xhs or dy...")


async def main():
    # define command line params
    parser = argparse.ArgumentParser(description="short video crawler platform.")
    parser.add_argument('--platform', type=str, help="short video platform (xhs|dy)", default=config.platform[0])
    parser.add_argument('--keywords', type=str, help="search note or page keywords.....")
    parser.add_argument('--lt', type=str, help="login type qrcode or phone", default=config.login_type[0])
    parser.add_argument('--web_session', type=str, help='cookies to keep login', default=config.login_web_session)
    parser.add_argument('--phone', type=str, help='login phone', default=config.login_phone)
    args = parser.parse_args()
    crawler = CrawlerFactory().get_crawler(args.platform)
    crawler.init_spider(
        keywords=args.keywords,
        login_phone=args.phone,
        login_type=args.lt,
        web_session=args.web_session,
    )
    await crawler.start_spider()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit()
