from enum import IntEnum
from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
from typing import Any
from xml.dom import NotFoundErr
import requests
from astropy.io import fits

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
          if devNameKeyword in name:
            self.name = name
            return

      except RuntimeError:
        raise NotFoundErr("Device not found")
    raise NotFoundErr("Device not found")

  def close(self):
    self.session.close()
    self.session = None

  def _get(self, cmd: str) -> Any:
    r = self.session.get(f'{self.url_root}/{self.devno}/{cmd}', params={"ClientID": self.client_id})
    if r.status_code != 200:
      raise RuntimeError(r.status_code)
    data = r.json()
    if data['ErrorNumber'] != 0:
      raise RuntimeError(data.ErrorMessage)
    return data['Value']

  def _put(self, cmd: str, val: dict) -> Any:
    data={"ClientID": self.client_id}
    data.update(val)
    r = self.session.put(f'{self.url_root}/{self.devno}/{cmd}', data=data)
    if r.status_code != 200:
      raise RuntimeError(r.status_code)
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

  @property
  def temperature(self) -> float:
    return self._get('ccdtemperature')

  class CameraState(IntEnum):
    IDLE = 0
    WAITING = 1
    EXPOSING = 2
    READING = 3
    DOWNLOAD = 4
    ERROR = 5

  @property
  def state(self) -> CameraState:
    return self._get('camerastate')

  """ Thermal """
  @property
  def cooler(self) -> bool:
    return self._get('cooleron')

  @property
  def coolerpower(self) -> float:
    return self._get('coolerpower')

  def coolto(self, tgt_tmp: float):
    pass

  def warmto(self, tgt_tmp: float):
    pass


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
    return self._get('gain')

  @gain.setter
  def gain(self, val):
    self._put('gain', {'Gain': val})


  """ Offset """
  @property
  def offsetmin(self) -> float:
    if not hasattr(self, '_offsetmin'):
      self._offsetmin = self._get('offsetmin')
    return self._offsetmin

  @property
  def offsetmax(self) -> float:
    if not hasattr(self, '_offsetmax'):
      self._offsetmax = self._get('offsetmax')
    return self._offsetmax

  @property
  def offset(self) -> float:
    return self._get('offset')

  @offset.setter
  def offset(self, val):
    self._put('offset', {'offset': val})


  """ Binning """
  @property
  def binning(self) -> int:
    return self._get('binx')

  @binning.setter
  def binning(self, val: int):
    self._put('binx', {'BinX': val})
    self._put('biny', {'BinY': val})


  """ Capture """ 
  def start_exposure(self, duration: float, light: bool = True):
    self._put('startexposure', {'Duration': duration, 'Light': light})

  @property
  def imageready(self) -> bool:
    return self._get('imageready')

  def getimage(self) -> str:
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

      date_obs = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
      hdr = fits.Header(
        {
          'COMMENT': 'Anand Dinakar',
          'OBJECT': self.objectName if self.objectName is not None else "Unk",
          'INSTRUME': self.name,
          'DATE-OBS': date_obs,
          'CAMERA-DATE-OBS': date_obs,
          'EXPTIME': exp_time,
          'CCD-TEMP': c.temperature,
          'BZERO': c.bzero, #32768,
          'BSCALE': c.bscale, #1 ,
          'XPIXSZ': c.pixelSize[0], #4.63,
          'YPIXSZ': c.pixelSize[1], #4.63,
          'XBINNING': binning,
          'YBINNING': binning,
          'XORGSUBF': 0,
          'YORGSUBF': 0,
          'EGAIN': c.egain, # 1.00224268436432,  # Electronic gain in e-/ADU.
          'FOCALLEN': focal_length,
          'JD': 2459795.74265046,
          'SWCREATE': 'AstroCAM',
          'SBSTDVER': 'SBFITSEXT Version 1.0',
          'SNAPSHOT': 1,
          'SET-TEMP': 0.0,
          'IMAGETYP': 'Light Frame',
          'SITELAT': '+40 51 55.000',
          'SITELONG': '-74 20 42.000',
          'GAIN': 120,
          'OFFSET': 0,
          'BAYERPAT': 'RGGB'
        }
      )

      hdu = fits.PrimaryHDU(img, header=hdr)
      hdu.writeto('output.fits')


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

  fname = c.getimage()
  print(fname)

  c.close()
