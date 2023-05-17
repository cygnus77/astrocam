
class Focuser():
  def __init__(self, devNameKeyword: str):
    super().__init__("focuser", devNameKeyword)
    self._position = 0

  @property
  def position(self):
    return self._position

  def movein(self, steps):
    self._position -= steps

  def moveout(self, steps):
    self._position += steps

  def goto(self, tgt):
    self._position = tgt
