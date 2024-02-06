import tkinter as tk
import tkinter.ttk as ttk
from image_data import ImageData
from ui.base_widget import BaseWidget
from pathlib import Path
import time
import math
import numpy as np

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
    self.minima = self.focuser.position
    self.search_width = 40
    self.state = 1
    self.astrocam.onImageReady.append(self._imageRetrieved)
    self.astrocam.takeSnapshot()
    self.fwhms = []

  def _imageRetrieved(self, imageData: ImageData):
    fname = Path(imageData.fname)
    fname = fname.rename(fname.parent / f"{fname.stem}_focus{self.focuser.position}{fname.suffix}")
    fwhm = np.sqrt(imageData.starData.fwhm_x**2 + imageData.starData.fwhm_y**2).mean()
    self.fwhms.append((self.focuser.position, fwhm))

    if self.state == 1:
      self.focuser.goto(self.minima - self.search_width)
    elif self.state == 2:
      self.focuser.goto(self.minima + self.search_width)
    elif self.state == 3:
      self.focuser.goto(self.minima - (self.search_width // 2))
    elif self.state == 4:
      self.focuser.goto(self.minima + (self.search_width // 2))
    elif self.state == 5:
      # fit curve
      coeffs = np.polyfit([x[0] for x in self.fwhms], [x[1] for x in self.fwhms])
      if coeffs[0] < 0:
        # failed
        self.state = 0
        print(f"Fit failed: {coeffs}")
      # calc new minima
      self.minima = int(-coeffs[1]/2*coeffs[0])
      # reset fwhms
      # self.fwhms = []
      self.state = 0
      # reduce search_width
      self.search_width = self.search_width // 2
      # if search_width < 5 stop
      if self.search_width < 5:
        self.focuser.goto(self.minima)
        return

    time.sleep(5)
    self.astrocam.onImageReady.append(self._imageRetrieved)
    self.astrocam.takeSnapshot()  
    self.state += 1
