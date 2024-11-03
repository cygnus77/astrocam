from ctypes import *
import time
from enum import IntEnum
import typing as T
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import ICRS


class CameraState(IntEnum):
    IDLE = 0
    EXPOSING = 1
    DOWNLOADING = 2
    ERROR = -1


class SensorType(IntEnum):
  MONO=0
  RGB=1 # Colour not requiring Bayer decoding
  RGGB=2
  CMYG=3
  CMYG2=4
  LRGB=5


class Scope:
    def __init__(self):
        self.api = cdll.LoadLibrary("./build/libcam.so")

        self.api.Initialize.argtypes = []
        self.api.Initialize.restype = c_bool
        self.api.Close.argtypes = []
        self.api.Close.restype = None
        self.api.Sleep1Sec.argtypes = []
        self.api.Sleep1Sec.restype = None

        self.api.getCameraModel.argtypes = []
        self.api.getCameraModel.restype = c_char_p
        self.api.getCameraState.argtypes = []
        self.api.getCameraState.restype = c_int
        self.api.getCameraConnected.argtypes = []
        self.api.getCameraConnected.restype = c_bool
        self.api.getCameraWidth.argtypes = []
        self.api.getCameraWidth.restype = c_double
        self.api.getCameraHeight.argtypes = []
        self.api.getCameraHeight.restype = c_double
        self.api.getCameraPixelSize.argtypes = []
        self.api.getCameraPixelSize.restype = c_double
        self.api.getCameraPixelWidth.argtypes = []
        self.api.getCameraPixelWidth.restype = c_double
        self.api.getCameraPixelHeight.argtypes = []
        self.api.getCameraPixelHeight.restype = c_double
        self.api.setCameraFrameType.argtypes = [c_bool]
        self.api.setCameraFrameType.restype = None
        self.api.cameraStartExposure.argtypes = [c_double]
        self.api.cameraStartExposure.restype = None
        self.api.getCameraImage.argtypes = [POINTER(c_void_p), POINTER(c_ulong)]
        self.api.getCameraImage.restype = None
        self.api.setCameraCoolerOn.argtypes = [c_bool]
        self.api.setCameraCoolerOn.restype = None
        self.api.getCameraCoolerOn.argtypes = []
        self.api.getCameraCoolerOn.restype = c_bool
        self.api.setCameraCoolerTemperature.argtypes = [c_double]
        self.api.setCameraCoolerTemperature.restype = None
        self.api.getCameraCoolerTemperature.argtypes = []
        self.api.getCameraCoolerTemperature.restype = c_double
        self.api.getCameraCoolerPower.argtypes = []
        self.api.getCameraCoolerPower.restype = c_double
        self.api.setCameraGain.argtypes = [c_double]
        self.api.setCameraGain.restype = None
        self.api.getCameraGain.argtypes = []
        self.api.getCameraGain.restype = c_double
        self.api.setCameraOffset.argtypes = [c_double]
        self.api.setCameraOffset.restype = None
        self.api.getCameraOffset.argtypes = []
        self.api.getCameraOffset.restype = c_double

        self.api.setFocuserPosition.argtypes = [c_double]
        self.api.setFocuserPosition.restype = None
        self.api.getFocuserPosition.argtypes = []
        self.api.getFocuserPosition.restype = c_double

        self.api.MountMoveTo.argtypes = [c_double, c_double]
        self.api.MountMoveTo.restype = None
        self.api.MountSyncTo.argtypes = [c_double, c_double]
        self.api.MountSyncTo.restype = None
        self.api.MountPark.argtypes = [c_bool]
        self.api.MountPark.restype = None
        self.api.MountGotoHome.argtypes = []
        self.api.MountGotoHome.restype = None
        self.api.getMountCoordinates.argtypes = [POINTER(c_double), POINTER(c_double)]
        self.api.getMountCoordinates.restype = None
        self.api.getMountTracking.argtypes = []
        self.api.getMountTracking.restype = c_bool
        self.api.getMountParked.argtypes = []
        self.api.getMountParked.restype = c_bool
        self.api.getMountSlewing.argtypes = []
        self.api.getMountSlewing.restype = c_bool
        self.api.getMountAtHome.argtypes = []
        self.api.getMountAtHome.restype = c_bool

        self.api.Initialize()

    def getCamera(self):
        return Camera(self.api)
    
    def getFocuser(self):
        return Focuser(self.api)
    
    def getMount(self):
        return Mount(self.api)

    def close(self):
        self.api.Close()

class Camera:
    """ Camera API """
    def __init__(self, api):
        self.api = api

    def isSimulator(self):
        return False

    """ Camera Info """
    @property
    def connected(self) -> bool:
        return self.api.getCameraConnected()

    @property
    def description(self) -> str:
        return self.api.getCameraModel().value()
    
    @property
    def name(self) -> str:
        return self.api.getCameraModel().value()
    
    @property
    def sensor_type(self) -> SensorType:
        return SensorType.RGGB

    @property
    def state(self) -> CameraState:
        return self.api.getCameraState()

    @property
    def pixelSize(self) -> T.List[float]:
        return [ self.api.getCameraPixelWidth(),
                 self.api.getCameraPixelHeight() ]

    """ Binning """
    @property
    def binning(self) -> int:
        return 1

    @binning.setter
    def binning(self, value: int):
        return

    """ Gain """
    @property
    def gain(self):
        return self.api.getCameraGain()
    
    @property
    def egain(self):
        return self.gain

    @gain.setter
    def gain(self, value):
        self.api.setCameraGain(value)

    @property
    def gainmin(self):
        return 0

    @property
    def gainmax(self):
        return 1e5

    """ Offset """
    @property
    def offset(self):
        return self.api.getCameraOffset()
    
    @property
    def offsetmin(self):
        return 0
    
    @property
    def offsetmax(self):
        return 100
    
    @offset.setter
    def offset(self, value):
        self.api.setCameraOffset(value)

    """ Thermal """
    @property
    def cooler(self) -> bool:
        return self.api.getCameraCoolerOn()


    @cooler.setter
    def cooler(self, value: bool):
        self.api.setCameraCoolerOn(True)

    @property
    def coolerpower(self) -> float:
        return self.api.getCameraCoolerPower()

    @property
    def temperature(self) -> float:
        return self.api.getCameraCoolerTemperature()

    @property
    def set_temp(self) -> float:
        return self.cooler_set_point
    
    @set_temp.setter
    def set_temp(self, tgt_temp: float):
        self.cooler_set_point = tgt_temp
        self.api.setCameraCoolerTemperature(self.cooler_set_point)

    """ Exposure """
    def start_exposure(self, durationSec: float, light: bool = True):
        self.api.setCameraFrameType(light)
        self.api.cameraStartExposure(durationSec)

    @property
    def imageready(self) -> bool:
        if self.state != CameraState.IDLE:
            return False
        image_ptr = c_void_p()
        image_len = c_ulong()
        self.api.getCameraImage(byref(image_ptr), byref(image_len))
        return image_len.value > 0 and image_ptr.value != 0

    def downloadimage(self) -> np.ndarray:
        image_ptr = c_void_p()
        image_len = c_ulong()
        image_width = self.api.getCameraWidth()
        image_width = self.api.getCameraHeight()
        self.api.getCameraImage(byref(image_ptr), byref(image_len))
        image_data = cast(image_ptr, POINTER(c_ubyte * image_len.value)).contents
        img = np.frombuffer(image_data, dtype=np.uint8)
        img = img.reshape((image_width, image_width, 3))
        return img

    def coolto(self, tgt_temp: float):
        # Gradually cool
        delta = self.temperature - tgt_temp
        if not self.cooler:
            self.cooler = True
        steps = 0
        while delta > 3 and steps < 50:
            step_end = self.temperature - 1
            self.set_temp = max(step_end, tgt_temp)

            step_retry = 15
            while (self.temperature > step_end or self.coolerpower > 60) and step_retry > 0:
                time.sleep(1)
                step_retry -= 1
            
            # Wait at this step
            time.sleep(4)
            delta = self.temperature - tgt_temp
            steps += 1
        self.set_temp = tgt_temp

    def warmto(self, tgt_temp: float):
        # Gradually cool
        delta = tgt_temp - self.temperature
        if not self.cooler:
            self._put("cooleron", {"CoolerOn": True})
        steps = 0
        while delta > 3 and steps < 50:
            step_end = self.temperature + 1
            self.set_temp = min(step_end, tgt_temp)

            step_retry = 10
            while self.temperature < step_end and step_retry > 0:
                time.sleep(1)
                step_retry -= 1

            # Wait at this step
            time.sleep(4)
            delta = tgt_temp - self.temperature
            steps += 1
        self.set_temp = tgt_temp
        self.cooler = False

class Focuser:
    """ Focuser API """
    def __init__(self, api):
        self.api = api

    @property
    def position(self):
        return self.api.getFocuserPosition()

    def movein(self, steps):
        pos = self.api.getFocuserPosition()
        pos -= steps
        self.api.setFocuserPosition(pos)
        return

    def moveout(self, steps):
        pos = self.api.getFocuserPosition()
        pos += steps
        self.api.setFocuserPosition(pos)
        return

    def goto(self, tgt):
        self.api.setFocuserPosition(tgt)

class Mount:
    """ Mount API """
    def __init__(self, api):
        self.api = api

    @property
    def coordinates(self) -> SkyCoord:
        ra = c_double()
        dec = c_double()
        self.api.getMountCoordinates(byref(ra), byref(dec))
        return SkyCoord(ra.value * u.hour, dec.value * u.degree, frame=ICRS)

    @property
    def site_lat(self):
        return None

    @property
    def site_lat(self):
        return None

    @property
    def tracking(self):
        return self.api.getMountTracking()

    @property
    def slewing(self):
        return self.api.getMountSlewing()

    @property
    def atpark(self):
        return self.api.getMountParked()

    def moveto(self, coord: SkyCoord):
        self.api.MountMoveTo(coord.ra.hour, coord.dec.degree)

    def syncto(self, coord: SkyCoord):
        self.api.MountSyncTo(coord.ra.hour, coord.dec.degree)

    def park(self, on):
        if on:
            self.api.MountGotoHome()
            while not self.api.getMountAtHome():
                self.api.Sleep1Sec()
        self.api.MountPark(on)

    def unpark(self):
        self._put("unpark", {})

if __name__ == "__main__":
    scope = Scope()
    cam = scope.getCamera()
    focuser = scope.getFocuser()
    mount = scope.getMount()

    # focuser.goto(10)

    mount.park(False)
    print("Starting coordinates: ", mount.coordinates)

    c = SkyCoord.from_name("Arcturus")
    print("Going to: ", c)
    mount.moveto(c)
    for i in range(20):
        print("Coordinates: ", mount.coordinates)
        scope.api.Sleep1Sec()

    scope.close()
