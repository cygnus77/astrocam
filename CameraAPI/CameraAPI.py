import ctypes

lib = ctypes.windll.LoadLibrary(r"C:\src\astrocam\CameraAPI\x64\Release\CameraAPI.dll")

iso_map = {
    "LO-1": 0,
    "LO-0.7": 1,
    "LO-0.3": 2,
    100: 3,
    125: 4,
    160: 5,
    200: 6,
    250: 7,
    320: 8,
    400: 9,
    500: 10,
    640: 11,
    800: 12,
    1000: 13,
    1250: 14,
    1600: 15,
    2000: 16,
    2500: 17,
    3200: 18,
    4000: 19,
    5000: 20,
    6400: 21,
    8000: 22,
    10000: 23,
    12800: 24,
    "Hi-0.3": 25,
    "Hi-0.7": 26,
    "Hi-1.0": 27,
    "Hi-2.0": 28
}

class Camera(object):
    def __init__(self, cameraId, destDir=None):
        lib.getCameraAPI.argtypes = []
        lib.getCameraAPI.restype = ctypes.c_void_p

        lib.open.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
        lib.open.restype = ctypes.c_int

        lib.setISO.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.setISO.restype = ctypes.c_int

        lib.takePicture.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.takePicture.restype = ctypes.c_int

        lib.close.argtypes = [ctypes.c_void_p]
        lib.close.restype = ctypes.c_int

        self.obj = lib.getCameraAPI()
        lib.open(self.obj, cameraId, destDir)

    def setISO(self, iso):
        return lib.setISO(self.obj, iso_map[iso])

    def takePicture(self, secs):
        return lib.takePicture(self.obj, secs)
    
    def close(self):
        lib.close(self.obj)
        self.obj = None
