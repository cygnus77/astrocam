from enum import IntEnum
from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
import typing as T

from Alpaca.alpaca_base import AscomDevice


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

  def goto(self, tgt):
    self._put("move", {"Position": tgt})


