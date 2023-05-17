
class SimulatedFocuser():

  def __init__(self):
    super().__init__()
    self._position = 0

  def close(self):
      return

  @property
  def position(self):
    return self._position

  def movein(self, steps):
    self._position -= steps

  def moveout(self, steps):
    self._position += steps

  def goto(self, tgt):
    self._position = tgt
