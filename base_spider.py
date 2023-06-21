from abc import ABC, abstractmethod


class Spider(ABC):
    @abstractmethod
    def init_spider(self, **kwargs):
        pass

    @abstractmethod
    async def start_spider(self):
        pass

    @abstractmethod
    async def login(self):
        pass

    @abstractmethod
    async def search_posts(self):
        pass

    @abstractmethod
    async def get_comments(self, item_id: int):
        """
        获得评论
        :param item_id:
        :return:
        """
        pass
