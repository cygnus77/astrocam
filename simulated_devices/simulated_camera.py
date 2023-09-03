
from pathlib import Path
import time
from enum import IntEnum
from astropy.io import fits
import numpy as np


class SensorType(IntEnum):
  MONO=0
  RGB=1 # Colour not requiring Bayer decoding
  RGGB=2
  CMYG=3
  CMYG2=4
  LRGB=5

class SimulatedCamera():
    def __init__(self, imgSrcFolder) -> None:
        self.dir = Path(imgSrcFolder)
        self._connected = True
        self._temperature = 22
        self._exp_start_time = None
        self._idx = 0
        self.files = list(self.dir.glob("*.fit"))

    def close(self):
        self._connected = False
        return
    
    def isSimulator(self):
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def description(self) -> str:
        return "Simulated Camera"
    
    @property
    def name(self) -> str:
        return "Simulated Camera"
    
    @property
    def sensor_type(self) -> SensorType:
        return SensorType.RGGB
    
    @property
    def state(self):
        return 0
    
    @property
    def pixelSize(self) -> float:
        return (1.0, 1.0)

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
        return 1
    
    @property
    def gainmin(self):
        return 1
    
    @property
    def gainmax(self):
        return 1
    
    @property
    def egain(self):
        return 1
    
    @gain.setter
    def gain(self, value):
        return
    
    """ Offset """
    @property
    def offset(self):
        return 1
    
    @property
    def offsetmin(self):
        return 1
    
    @property
    def offsetmax(self):
        return 1
    
    @offset.setter
    def offset(self, value):
        return

    """ Temperature """
    @property
    def cooler(self):
        return True
    
    @cooler.setter
    def cooler(self, value: bool):
        return

    @property
    def coolerpower(self) -> float:
        return 50.0

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def set_temp(self) -> float:
        return 0

    @set_temp.setter
    def set_temp(self, value: float):
        return

    def coolto(self, tgt_temp: float):
        while self._temperature > tgt_temp:
            self._temperature -= 0.1
            time.sleep(1)
    
    def warmto(self, tgt_temp: float):
        while self._temperature < tgt_temp:
            self._temperature += 0.1
            time.sleep(1)

    """ Exposure """
    def start_exposure(self, durationSec: float, light: bool = True):
        self._exp_start_time = time.time()
        self._durationSec = durationSec
        print("Started exposure")

    @property
    def imageready(self) -> bool:
        if not self._connected:
            return False
        if time.time() - self._exp_start_time > self._durationSec:
            self._exp_start_time = None
            print("Image ready")
            return True
        return False

    def downloadimage(self):
        fname = self.files[self._idx % len(self.files)]
        print(fname)
        self._idx += 1
        with fits.open(fname) as f:
            ph = f[0]
            img = ph.data
            print("Image delivered")
            return np.expand_dims(img, axis=2)
