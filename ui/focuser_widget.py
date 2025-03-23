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
    buttonFrame = ttk.Frame(gotoFrame)
    buttonFrame.pack(fill=tk.X)

    ttk.Button(buttonFrame, text="\u21e7", command=lambda: self.focuser.movein(5)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u2191", command=lambda: self.focuser.movein(1)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u2193", command=lambda: self.focuser.moveout(1)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u21e9", command=lambda: self.focuser.moveout(5)).pack(side=tk.LEFT, fill=tk.X, padx=2)

    controlFrame = ttk.Frame(gotoFrame)
    controlFrame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Entry(controlFrame, textvariable=self.focuserGotoTgt, font=BaseWidget.EntryFont, width=BaseWidget.EntryWidth).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    ttk.Button(controlFrame, text="Goto", command=self.focuserGoto, style='X.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    ttk.Button(controlFrame, text='Refine', command=self._refine).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

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
    self.bounds = (self.minima - self.search_width, self.minima + self.search_width)
    self.state = 1
    self.astrocam.onImageReady.append(self._fitParabola)
    self.astrocam.takeSnapshot(iso_override=200, exp_override=5.0)
    self.tgt_fwhm = None
    self.fwhms = []

  def _fitParabola(self, imageData: ImageData):
    fname = Path(imageData.fname)
    fname = fname.rename(fname.parent / f"{fname.stem}_focus{self.focuser.position}{fname.suffix}")
    fwhm = np.sqrt(imageData.stars.fwhm_x**2 + imageData.stars.fwhm_y**2).mean()
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
      coeffs = np.polyfit([x[0] for x in self.fwhms], [x[1] for x in self.fwhms], deg=2)
      if coeffs[0] < 0:
        # failed
        self.state = 0
        print(f"Fit failed: {coeffs}")
        return
      # calc new minima
      self.minima = int(-coeffs[1]/(2*coeffs[0]))
      self.tgt_fwhm = np.polyval(coeffs, self.minima)
      if self.minima < self.bounds[0]:
        self.minima = self.bounds[0]
      elif self.minima > self.bounds[1]:
        self.minima = self.bounds[1]
      # reset fwhms
      self.state = 0
      # # reduce search_width
      # self.search_width = int(self.search_width * 2 / 3)
      # # if search_width < 5 stop
      # if self.search_width < 10:
      #   self.focuser.goto(self.minima)
      #   return
      self.focuser.goto(self.minima - self.search_width // 2)
      self.astrocam.onImageReady.append(self._scanMinima)
      self.astrocam.takeSnapshot(iso_override=200, exp_override=5.0)  
      return

    time.sleep(5)
    self.astrocam.onImageReady.append(self._fitParabola)
    self.astrocam.takeSnapshot(iso_override=200, exp_override=5.0)  
    self.state += 1

  def _scanMinima(self, imageData: ImageData):
    fname = Path(imageData.fname)
    fname = fname.rename(fname.parent / f"{fname.stem}_focus{self.focuser.position}{fname.suffix}")
    fwhm = np.sqrt(imageData.stars.fwhm_x**2 + imageData.stars.fwhm_y**2).mean()
    if fwhm < self.tgt_fwhm+1:
      print(f"Done ! FWHM: {fwhm}")
      return
    self.fwhms.append((self.focuser.position, fwhm))

    if self.focuser.position < (self.minima + self.search_width // 2):
      self.focuser.goto(self.focuser.position + 2)
      self.astrocam.onImageReady.append(self._scanMinima)
      self.astrocam.takeSnapshot(iso_override=200, exp_override=5.0)
    else:
      final_fwhm, final_pos = np.min(self.fwhms, key=lambda x: x[0])
      self.focuser.goto(final_pos)
