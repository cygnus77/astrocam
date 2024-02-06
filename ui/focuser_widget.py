import tkinter as tk
import tkinter.ttk as ttk
from image_data import ImageData
from ui.base_widget import BaseWidget
from pathlib import Path
import time

class FocuserWidget(BaseWidget):
  def __init__(self, parentFrame, astrocam, device):
    super().__init__(parentFrame, "Focuser")

    self.focuserGotoTgt = tk.IntVar()
    self.focuser = device
    self.astrocam = astrocam

    gotoFrame = ttk.Frame(self.widgetFrame)
    ttk.Button(gotoFrame, text="\u21e7", command=lambda evt: self.focuser.movein(5))
    ttk.Button(gotoFrame, text="\u2191", command=lambda evt: self.focuser.movein(1))
    ttk.Entry(gotoFrame,textvariable=self.focuserGotoTgt, font=BaseWidget.EntryFont, width=BaseWidget.EntryWidth).pack(side=tk.LEFT, fill=tk.X)
    ttk.Button(gotoFrame, text="Goto", command=self.focuserGoto, style='X.TButton').pack(side=tk.RIGHT)
    ttk.Button(gotoFrame, text="\u2193", command=lambda evt: self.focuser.moveout(5))
    ttk.Button(gotoFrame, text="\u21e9", command=lambda evt: self.focuser.moveout(1))

    ttk.Button(gotoFrame, text='Refine', command=self._refine).pack(side=tk.LEFT)
    gotoFrame.pack(fill=tk.X)

  def _connect(self, focuser):
    self.focuser = focuser

  def _disconnect(self):
    self.focuser = None

  def focuserGoto(self):
    try:
      if self.focuser is not None and self.focuser.connected:
        self.focuser.goto(self.focuserGotoTgt.get())
    except Exception as e:
      print("Error moving focuser: {e}")

  def onkeypress(self, event):
    try:
      if self.focuser is not None and self.focuser.connected:
        if event.char == 'i':
          self.focuser.movein(1)
        elif event.char == 'I':
          self.focuser.movein(5)
        elif event.char == 'o':
          self.focuser.moveout(1)
        elif event.char == 'O':
          self.focuser.moveout(5)
    except Exception as e:
      print("Error moving focuser: {e}")

  def _update(self):
    if self.focuser is not None and self.focuser.connected:
      self.hdrInfo.set(self.focuser.position)
      return True
    return False


  def _refine(self):
    self.reset_pos = self.focuser.position
    self.min = self.reset_pos - 30
    self.max = self.reset_pos + 30
    self.mode = 1
    self.astrocam.onImageReady.append(self._imageRetrieved)
    self.astrocam.takeSnapshot()

  def _imageRetrieved(self, imageData: ImageData):
    fname = Path(imageData.fname)
    fname = fname.rename(fname.parent / f"{fname.stem}_focus{self.focuser.position}{fname.suffix}")
    print(fname)

    if self.mode == 1:
      self.focuser.movein(5)
      time.sleep(2)
      self.astrocam.onImageReady.append(self._imageRetrieved)
      self.astrocam.takeSnapshot()
      if self.focuser.position <= self.min:
        self.mode = 2
    elif self.mode == 2:
      self.focuser.moveout(5)
      time.sleep(2)
      self.astrocam.onImageReady.append(self._imageRetrieved)
      self.astrocam.takeSnapshot()
      if self.focuser.position >= self.max:
        self.mode = 0
        self.focuser.goto(self.reset_pos)
