import numpy as np
import zwoasi as asi
from enum import IntEnum
import time
from pathlib import Path

library_file = Path(__file__).parent/"lib/x64/ASICamera2.dll"
asi.init(library_file=str(library_file))

class SensorType(IntEnum):
  MONO=0
  RGB=1 # Colour not requiring Bayer decoding
  RGGB=2
  CMYG=3
  CMYG2=4
  LRGB=5

class ASINativeCamera():
    
  def __init__(self, cameraModel) -> None:
    id = None
    for idx, cam_name in enumerate(asi.list_cameras()):
      if cameraModel in cam_name:
        id = idx
        break
    if id is None:
      raise ValueError("Camera not found")

    self.camera = asi.Camera(id)
    self.camera_info = self.camera.get_camera_property()
    print("Camera info:")
    for k,v in self.camera_info.items():
      print('\t', k, v)
    print()
    print("Controls:")
    print('')
    print('Camera controls:')
    controls = self.camera.get_controls()
    for cn in sorted(controls.keys()):
        print('    %s:' % cn)
        for k in sorted(controls[cn].keys()):
            print('        %s: %s' % (k, repr(controls[cn][k])))
    print()
    self._connected = True

    # Defaults
    self.camera.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, self.camera.get_controls()['BandWidth']['MaxValue'])
    self.camera.disable_dark_subtract()
    self.camera.stop_video_capture()
    self.camera.stop_exposure()
    self.camera.set_image_type(asi.ASI_IMG_RAW16)
    self.gain = 121
    self.offset = 30
    self._buffer = None

  def close(self):
    self._connected = False
    self.camera.close()

  def isSimulator(self):
    return False

  """ Camera Info """
  @property
  def connected(self) -> bool:
      return self._connected
  
  @property
  def description(self) -> str:
    return self.camera_info['Name']
  
  @property
  def name(self) -> str:
    return self.camera_info['Name']
   
  @property
  def sensor_type(self) -> SensorType:
    if not self.camera_info['IsColorCam']:
      return SensorType.MONO
    else:
      if self.camera_info['BayerPattern'] == asi.ASI_BAYER_RG:
        return SensorType.RGGB
      else:
        return SensorType.RGB

  @property
  def state(self) -> IntEnum:
    return self.camera.get_camera_mode()

  @property
  def pixelSize(self) -> float:
    pixsize = self.camera_info['PixelSize']
    return (pixsize, pixsize)

  """ Binning """
  @property
  def binning(self) -> int:
    return self.camera.get_bin()

  @binning.setter
  def binning(self, value: int):
    self.camera.set_roi(bins=value)

  """ Gain """
  @property
  def gain(self):
    return self.camera.get_control_value(asi.ASI_GAIN)[0]
  
  @property
  def egain(self):
    return self.gain

  @gain.setter
  def gain(self, value):
    self.camera.set_control_value(asi.ASI_GAIN, value)

  @property
  def gainmin(self):
    return self.camera.get_controls()['Gain']['MinValue']

  @property
  def gainmax(self):
    return self.camera.get_controls()['Gain']['MaxValue']

  """ Offset """
  @property
  def offset(self):
    return self.camera.get_control_value(asi.ASI_OFFSET)[0]
  
  @property
  def offsetmin(self):
    return self.camera.get_controls()['Offset']['MinValue']
  
  @property
  def offsetmax(self):
    return self.camera.get_controls()['Offset']['MaxValue']
  
  @offset.setter
  def offset(self, value):
    self.camera.set_control_value(asi.ASI_OFFSET, value)

  """ Temperature """
  @property
  def cooler(self):
    return self.camera.get_control_value(asi.ASI_COOLER_ON)[0]
  
  @cooler.setter
  def cooler(self, value: bool):
    self.camera.set_control_value(asi.ASI_COOLER_ON, 1 if value else 0)

  @property
  def coolerpower(self) -> float:
    return self.camera.get_control_value(asi.ASI_COOLER_POWER_PERC)[0]

  @property
  def temperature(self) -> float:
    return self.camera.get_control_value(asi.ASI_TEMPERATURE)[0] / 10.0

  @property
  def set_temp(self) -> float:
    return self.camera.get_control_value(asi.ASI_TARGET_TEMP)[0]

  @set_temp.setter
  def set_temp(self, value: int):
    self.camera.set_control_value(asi.ASI_TARGET_TEMP, int(value))

  """ Exposure """
  def start_exposure(self, durationSec: float, light: bool = True):
    self.camera.set_control_value(asi.ASI_EXPOSURE, int(durationSec * 1e6))
    self.camera.start_exposure(is_dark=not light)

  @property
  def imageready(self) -> bool:
    exp_stat = self.camera.get_exposure_status()
    if exp_stat == asi.ASI_EXP_WORKING:
      return False
    elif exp_stat == asi.ASI_EXP_SUCCESS:
      return True
    else:
      raise ValueError(f"Exposure failed: {exp_stat}")

  def downloadimage(self):
    data = self.camera.get_data_after_exposure(self._buffer)
    whbi = self.camera.get_roi_format()
    shape = [whbi[1], whbi[0]]
    if whbi[3] == asi.ASI_IMG_RAW8 or whbi[3] == asi.ASI_IMG_Y8:
        img = np.frombuffer(data, dtype=np.uint8)
    elif whbi[3] == asi.ASI_IMG_RAW16:
        img = np.frombuffer(data, dtype=np.uint16)
    elif whbi[3] == asi.ASI_IMG_RGB24:
        img = np.frombuffer(data, dtype=np.uint8)
        shape.append(3)
    else:
        raise ValueError('Unsupported image type')
    self._buffer = data
    img = img.reshape(shape)
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
      while (self.temperature > step_end or self.coolerpower > 60)and step_retry > 0:
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


if __name__ == "__main__":
  from tqdm import tqdm
  import numpy as np
  camera = ASINativeCamera(0)
  print(camera.connected)
  print(camera.description)
  print(camera.sensor_type)
  print(camera.state)
  print(camera.cooler)
  camera.gain = 121
  camera.offset = 30
  durationSec = 0.05
  # # Photo shoot
  # for i in tqdm(range(20)):
  #   img = camera.start_exposure(0.05)
  # # Video shoot
  # camera.camera.set_control_value(asi.ASI_EXPOSURE, int(durationSec * 1e6))
  # camera.camera.start_video_capture()
  # buffer = None
  # timeout = 2 * durationSec * 1000 + 500
  # for i in tqdm(range(100)):
  #   buffer = camera.camera.get_video_data(timeout, buffer)
  #   img = np.frombuffer(buffer, dtype=np.uint8)
  camera.close()

