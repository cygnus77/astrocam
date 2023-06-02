from enum import IntEnum
from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
import typing as T

from Alpaca.alpaca_base import AscomDevice

class ASCOMImageArrayElementTypes(IntEnum):
  Unknown = 0
  Int16 = 1
  Int32 = 2
  Double = 3
  Single = 4
  UInt64 = 5
  Byte = 6
  Int64 = 7
  UInt16 = 8
  UInt32 = 9

class Camera(AscomDevice):
  def __init__(self, name):
    super().__init__("camera", name)
    self._egain = self._get("electronsperadu")
    self._pixelSize = [self._get("pixelsizex"), self._get("pixelsizey")]
    self._sensortype = self._get("sensortype")

  def isSimulator(self):
    return False

  class CameraState(IntEnum):
    IDLE = 0
    WAITING = 1
    EXPOSING = 2
    READING = 3
    DOWNLOAD = 4
    ERROR = 5

  @property
  def state(self) -> CameraState:
    return Camera.CameraState(self._get('camerastate'))

  class SensorType(IntEnum):
    MONO=0
    RGB=1 # Colour not requiring Bayer decoding
    RGGB=2
    CMYG=3
    CMYG2=4
    LRGB=5

  @property
  def sensor_type(self) -> SensorType:
    return Camera.SensorType(self._sensortype)

  @property
  def egain(self) -> float:
    return self._egain

  @property
  def pixelSize(self) -> T.List[float]:
    return self._pixelSize

  """ Thermal """
  @property
  def cooler(self) -> bool:
    return self._get('cooleron')

  @property
  def temperature(self) -> float:
    return self._get('ccdtemperature')

  @property
  def coolerpower(self) -> float:
    return self._get('coolerpower')

  @property
  def set_temp(self) -> float:
    return self._get('setccdtemperature')

  def _set_tgt_temp(self, tgt_temp):
    self._put("setccdtemperature", {"SetCCDTemperature": tgt_temp})

  def coolto(self, tgt_temp: float):
    # Gradually cool
    delta = self.temperature - tgt_temp
    if not self.cooler:
      self._put("cooleron", {"CoolerOn": True})
    steps = 0
    while delta > 3 and steps < 50:
      step_end = self.temperature - 1
      self._set_tgt_temp(max(step_end, tgt_temp))

      step_retry = 15
      while (self.temperature > step_end or self.coolerpower > 60)and step_retry > 0:
        time.sleep(1)
        step_retry -= 1
      
      # Wait at this step
      time.sleep(4)
      delta = self.temperature - tgt_temp
      steps += 1
    self._set_tgt_temp(tgt_temp)

  def warmto(self, tgt_temp: float):
    # Gradually cool
    delta = tgt_temp - self.temperature
    if not self.cooler:
      self._put("cooleron", {"CoolerOn": True})
    steps = 0
    while delta > 3 and steps < 50:
      step_end = self.temperature + 1
      self._set_tgt_temp(min(step_end, tgt_temp))

      step_retry = 10
      while self.temperature < step_end and step_retry > 0:
        time.sleep(1)
        step_retry -= 1

      # Wait at this step
      time.sleep(4)
      delta = tgt_temp - self.temperature
      steps += 1
    self._set_tgt_temp(tgt_temp)
    self._put("cooleron", {"CoolerOn": False})

  """ Offset """
  @property
  def gainmin(self) -> float:
    if not hasattr(self, '_gainmin'):
      self._gainmin = self._get('gainmin')
    return self._gainmin

  @property
  def gainmax(self) -> float:
    if not hasattr(self, '_gainmax'):
      self._gainmax = self._get('gainmax')
    return self._gainmax

  @property
  def gain(self) -> float:
    if not hasattr(self, '_gain'):
      self._gain = self._get('gain')
    return self._gain

  @gain.setter
  def gain(self, val):
    self._put('gain', {'Gain': val})
    self._gain = val


  """ Offset """
  @property
  def offsetmin(self) -> float:
    if not hasattr(self, '_offsetmin'):
      self._offsetmin = self._get('offsetmin', 0)
    return self._offsetmin

  @property
  def offsetmax(self) -> float:
    if not hasattr(self, '_offsetmax'):
      self._offsetmax = self._get('offsetmax', 0)
    return self._offsetmax

  @property
  def offset(self) -> float:
    if not hasattr(self, '_offset'):
      self._offset = self._get('offset', 0)
    return self._offset

  @offset.setter
  def offset(self, val):
    self._put('offset', {'offset': val})
    self._offset = val


  """ Binning """
  @property
  def binning(self) -> int:
    if not hasattr(self, '_bin'):
      self._bin = self._get('binx')
    return self._bin

  @binning.setter
  def binning(self, val: int):
    self._put('binx', {'BinX': val})
    self._put('biny', {'BinY': val})
    self._bin = val


  """ Capture """ 
  def start_exposure(self, duration: float, light: bool = True):
    self._put('startexposure', {'Duration': duration, 'Light': light})

  @property
  def imageready(self) -> bool:
    return self._get('imageready')

  def downloadimage(self) -> str:
    url = f'{self.url_root}/{self.devno}/imagearray'
    with self.session.get(url, headers={'Accept': "application/imagebytes"}) as r:
      buffer = r.content
      metdataVersion, errorNumber,\
        clientTransactionId, serverTransactionId,\
        dataStart, imageElementType,\
        transmissionElementType, rank,\
        dimension1, dimension2, dimension3 =  unpack('llLLlllllll', buffer[:44])
      print(metdataVersion, errorNumber,\
        clientTransactionId, serverTransactionId,\
        dataStart, imageElementType,\
        transmissionElementType, rank,\
        dimension1, dimension2, dimension3)

      assert(metdataVersion == 1)
      if errorNumber != 0:
        raise RuntimeError(f"Error downloading image: {errorNumber}")
      assert(rank == 2)
      assert(imageElementType == 2)

      if transmissionElementType == ASCOMImageArrayElementTypes.Byte:
        baseType = np.uint8
      elif transmissionElementType == ASCOMImageArrayElementTypes.Double:
        baseType = np.double
      elif transmissionElementType == ASCOMImageArrayElementTypes.Int16:
        baseType = np.int16
      elif transmissionElementType == ASCOMImageArrayElementTypes.Int32:
        baseType = np.int32
      elif transmissionElementType == ASCOMImageArrayElementTypes.Int64:
        baseType = np.int64
      elif transmissionElementType == ASCOMImageArrayElementTypes.Single:
        baseType = np.float32
      elif transmissionElementType == ASCOMImageArrayElementTypes.UInt16:
        baseType = np.uint16
      elif transmissionElementType == ASCOMImageArrayElementTypes.UInt32:
        baseType = np.uint32
      elif transmissionElementType == ASCOMImageArrayElementTypes.UInt64:
        baseType = np.uint64
      else:
        raise ValueError(f"Unexpected ASCOM transmission type: {transmissionElementType}")

      dt = np.dtype(baseType).newbyteorder('little')
      img = np.frombuffer(buffer[dataStart:], dtype=dt).reshape((dimension1, dimension2)).T

      return img


if __name__ == "__main__":

  c = Camera("294")
  print(c.description)
  print(f"Camera state: {c.state}, connected: {c.connected}, cooler: {c.cooler}, temperature: {c.temperature} ")
  c.gain = 390
  exp = 5
  c.start_exposure(exp)
  time.sleep(exp)

  while not c.imageready:
    print('waiting')
    time.sleep(1)

  fname = c.downloadimage()
  print(fname)

  c.close()