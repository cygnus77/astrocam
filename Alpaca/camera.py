from enum import IntEnum
from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
import typing as T
from xml.dom import NotFoundErr
import requests


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



class AscomDevice:
  def __init__(self, deviceType: str, devNameKeyword: str):
    self.deviceType = deviceType
    self.url_root = f'http://localhost:11111/api/v1/{self.deviceType}'
    self.client_id = 0
    self.session = requests.Session()

    for devno in range(10):
      self.devno = devno
      try:
        if self._get('connected') == True:
          name = self._get('name')
          if devNameKeyword.lower() in name.lower():
            self.name = name
            return

      except RuntimeError:
        raise NotFoundErr("Device not found")
    raise NotFoundErr("Device not found")

  def close(self):
    self.session.close()
    self.session = None

  def _get(self, cmd: str, defaultVal = None) -> T.Any:
    r = self.session.get(f'{self.url_root}/{self.devno}/{cmd}', params={"ClientID": self.client_id})
    if r.status_code != 200:
      raise RuntimeError(r.status_code)
    data = r.json()
    if data['ErrorNumber'] != 0:
      if data['ErrorNumber'] == 1024 or data['ErrorNumber'] == -2146233088: # NotImplemented
        return defaultVal
      raise RuntimeError(data.ErrorMessage)
    return data['Value']

  def _put(self, cmd: str, val: dict) -> T.Any:
    data={"ClientID": self.client_id}
    data.update(val)
    r = self.session.put(f'{self.url_root}/{self.devno}/{cmd}', data=data)
    if r.status_code != 200:
      raise RuntimeError(f"{r.status_code}: {r.content}")
    data = r.json()
    if data['ErrorNumber'] != 0:
      raise RuntimeError(data.ErrorMessage)

  @property
  def connected(self) -> bool:
    return self._get('connected')

  @property
  def description(self) -> str:
    if not hasattr(self,'_description'):
      self._description = self._get('description')
    return self._description


class Camera(AscomDevice):
  def __init__(self, name):
    super().__init__("camera", name)
    self._egain = self._get("electronsperadu")
    self._pixelSize = [self._get("pixelsizex"), self._get("pixelsizey")]
    self._sensortype = self._get("sensortype")

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
    while delta > 3 and steps < 25:
      self._set_tgt_temp(max(self.temperature - 3), tgt_temp)
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
    while delta > 3 and steps < 25:
      self._set_tgt_temp(min(self.temperature + 3), tgt_temp)
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


class Focuser(AscomDevice):
  def __init__(self, devNameKeyword: str):
    super().__init__("focuser", devNameKeyword)

  @property
  def position(self):
    return self._get("position")

  def movein(self, steps):
    pos = self._get("position")
    pos -= steps
    self._put("move", {"Position": pos})
    return

  def moveout(self, steps):
    pos = self._get("position")
    pos += steps
    self._put("move", {"Position": pos})
    return


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
