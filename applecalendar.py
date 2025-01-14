class AppleCalendar:
    def __init__(self, url: str, id: str, name: str):
        self.__url = url
        self.__id = id
        self.__name = name

    def get_url(self):
        return self.__url

    def get_id(self):
        return self.__id

    def get_name(self):
        return self.__name