import tkinter as tk
import tkinter.ttk as ttk
from image_data import ImageData
from ui.base_widget import BaseWidget
from pathlib import Path
import time
import math
import numpy as np
from focuser_service import FocuserService


class FocuserWidget(BaseWidget):
  def __init__(self, parentFrame, tk_root, focuser, camera):
    super().__init__(parentFrame, "Focuser")

    self.focuserGotoTgt = tk.IntVar()
    self._tk_root = tk_root
    self.focuser = focuser
    self.camera = camera

    gotoFrame = ttk.Frame(self.widgetFrame)
    buttonFrame = ttk.Frame(gotoFrame)
    buttonFrame.pack(fill=tk.X)

    ttk.Button(buttonFrame, text="\u21e7",
               command=lambda: self.focuser_svc.movein(5, on_failure=self._on_focuser_error)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u2191",
               command=lambda: self.focuser_svc.movein(1, on_failure=self._on_focuser_error)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u2193",
               command=lambda: self.focuser_svc.moveout(1, on_failure=self._on_focuser_error)).pack(side=tk.LEFT,  fill=tk.X, padx=2)
    ttk.Button(buttonFrame, text="\u21e9",
               command=lambda: self.focuser_svc.moveout(5, on_failure=self._on_focuser_error)).pack(side=tk.LEFT, fill=tk.X, padx=2)

    controlFrame = ttk.Frame(gotoFrame)
    controlFrame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Entry(controlFrame, textvariable=self.focuserGotoTgt, font=BaseWidget.EntryFont, width=BaseWidget.EntryWidth).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    ttk.Button(controlFrame, text="Goto", command=self.focuserGoto, style='X.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    ttk.Button(controlFrame, text='Refine', command=self.refine).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    gotoFrame.pack(fill=tk.X)

    self._tk_root.bind(FocuserService.AutofocusEventName, self._update_autofocus_status)


  def _connect(self, focuser, camera):
    self.focuser = focuser
    self.camera = camera
    self.focuser_svc = FocuserService(self._tk_root, self.focuser, self.camera)
    self._tk_root.bind(FocuserService.PositionUpdateEventName, self._update_focuser_position)

  def _disconnect(self):
    self.focuser = None

  def _on_focuser_error(self, job, error):
    self.status = self.EXCLAMATION
    self.hdrInfo.set(error)
  
  def _update_focuser_position(self, event):
    self.hdrInfo.set(str(event.y))

  def _update_autofocus_status(self, event):
    match event.x:
      case 0:
        self.hdrInfo.set(f"Autofocus started, start pos: {event.y}")
      case 1:
        self.hdrInfo.set(f"Autofocus minima: {event.y}")
      case 2:
        self.hdrInfo.set(f"Autofocus lowest: {event.y}")
      case 3:
        self.hdrInfo.set(f"Autofocus done: {event.y}")


  def focuserGoto(self):
    self.focuser_svc.goto(self.focuserGotoTgt.get(), on_failure=self._on_focuser_error)

  def onkeypress(self, event):
    if event.char == 'i':
      self.focuser_svc.movein(1, on_failure=self._on_focuser_error)
    elif event.char == 'I':
      self.focuser_svc.movein(5, on_failure=self._on_focuser_error)
    elif event.char == 'o':
      self.focuser_svc.moveout(1, on_failure=self._on_focuser_error)
    elif event.char == 'O':
      self.focuser_svc.moveout(5, on_failure=self._on_focuser_error)

  def _update(self):
    if self.focuser is not None and self.focuser.connected:
      self.hdrInfo.set(self.focuser.position)
      return True
    return False

  def refine(self):
    self.focuser_svc.autofocus(on_failure=self._on_focuser_error)

