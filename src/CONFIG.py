from typing import List


#
# class Point(object):
#
#     def __init__(self, dict_) -> None:
#         self.x = 0
#         self.y = 0
#         self.__dict__.update(dict_)
#
#
# class Zone(object):
#
#     def __init__(self, dict_) -> None:
#         self.zone_name = ""
#         self.points = []
#         self.__dict__.update(dict_)


class Config(object):

    def __init__(self, dict_) -> None:
        # self.height = 0
        # self.width = 0
        # self.skip_frames = 0
        # self.static_frames = 0
        # self.number_of_check = 0
        # self.enable_green_zone = 0
        # self.debug = False
        # self.storage_path = ""
        # self.post_url = ""
        # self.zones = []
        self.__dict__.update(dict_)


class MainConfig(object):

    def __init__(self, dict_) -> None:
        self.__dict__.update(dict_)

# from typing import List
#
#
# class Point:
#     x: int
#     y: int
#
#     def __init__(self, x: int, y: int, *args, **kwargs) -> None:
#         self.x = x
#         self.y = y
#
#
# class Zone(object):
#     zone_name: str
#     points: List[Point]
#
#     def __init__(self, zone_name: str, points: List[Point], *args, **kwargs) -> None:
#         self.zone_name = zone_name
#         self.points = points
#
#
# class Config(object):
#     height: int
#     width: int
#     skip_frames: int
#     static_frames: int
#     number_of_check: int
#     enable_green_zone: int
#     debug: bool
#     storage_path: str
#     post_url: str
#     zones: List[Zone]
#
#     def __init__(self, height: int, width: int, skip_frames: int, static_frames: int, number_of_check: int, enable_green_zone: int, debug: bool, storage_path: str, post_url: str, zones: List[Zone], *args, **kwargs) -> None:
#         self.height = height
#         self.width = width
#         self.skip_frames = skip_frames
#         self.static_frames = static_frames
#         self.number_of_check = number_of_check
#         self.enable_green_zone = enable_green_zone
#         self.debug = debug
#         self.storage_path = storage_path
#         self.post_url = post_url
#         self.zones = zones
