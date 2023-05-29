
class SimulatedFocuser():

  def __init__(self):
    super().__init__()
    self._connected = True
    self._position = 10000

  def close(self):
      self._connected = False
      return

  @property
  def connected(self):
    return self._connected

  @property
  def position(self):
    return self._position

  def movein(self, steps):
    self._position -= steps

  def moveout(self, steps):
    self._position += steps

  def goto(self, tgt):
    self._position = tgt
