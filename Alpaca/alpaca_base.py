from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
import typing as T
from xml.dom import NotFoundErr
import requests

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

      except RuntimeError as err:
        pass
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
      raise RuntimeError(data['ErrorMessage'])
    return data['Value']

  def _put(self, cmd: str, val: dict) -> T.Any:
    data={"ClientID": self.client_id}
    data.update(val)
    r = self.session.put(f'{self.url_root}/{self.devno}/{cmd}', data=data)
    if r.status_code != 200:
      raise RuntimeError(f"{r.status_code}: {r.content}")
    data = r.json()
    if data['ErrorNumber'] != 0:
      raise RuntimeError(data['ErrorMessage'])

  @property
  def connected(self) -> bool:
    return self._get('connected')

  @property
  def description(self) -> str:
    if not hasattr(self,'_description'):
      self._description = self._get('description')
    return self._description

