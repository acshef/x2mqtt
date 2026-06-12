__all__ = ["Origin"]


class Origin:
    name: str
    sw_version: str
    url: str | None

    __slots__ = ("name", "sw_version", "url")

    def __init__(self, name: str, sw_version: str | None = None, url: str | None = None):
        self.name = name
        self.sw_version = sw_version
        self.url = url

    def _asdict(self):
        obj = {
            "name": self.name,
        }
        if self.sw_version is not None:
            obj["sw"] = self.sw_version
        if self.url is not None:
            obj["url"]

        return obj
