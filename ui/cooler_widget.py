import tkinter as tk
import tkinter.ttk as ttk

from threading import Thread
from ui.base_widget import BaseWidget


class CoolerWidget(BaseWidget):
  def __init__(self, parentFrame, device):
    super().__init__()
    self.camera = device

    self.cameraTemp = tk.StringVar()
    self.cameraCooler = tk.StringVar()

    tempFrame = ttk.Frame(parentFrame)
    ttk.Button(tempFrame, text="Cool", command=self.coolCamera).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Label(tempFrame, textvariable=self.cameraTemp).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Button(tempFrame, text="Warm", command=self.warmCamera).pack(side=tk.LEFT, padx=5, pady=5)
    tempFrame.pack(fill=tk.X, side=tk.TOP)
    # Cooler & power status
    coolerFrame = ttk.Frame(parentFrame)
    ttk.Label(coolerFrame, textvariable=self.cameraCooler).pack(side=tk.LEFT, padx=5, pady=5)
    coolerFrame.pack(fill=tk.X, side=tk.TOP)

    self.thread = None

  def connect(self, camera):
    self.camera = camera

  def disconnect(self):
    self.camera = None

  def coolCamera(self):
    self.thread = Thread(target=self.camera.coolto, args=[0], name="Cool")
    self.thread.start()

  def warmCamera(self):
    self.thread = Thread(target=self.camera.warmto, args=[25], name="Warm")
    self.thread.start()

  def update(self):
    try:
      if self.camera is not None and self.camera.connected:

        threadStatus = ""      
        if self.thread is not None:
          if self.thread.is_alive():
            if self.thread.getName() == "Cool":
              # unicode char for arrow down
              threadStatus += u'\u2193'
            elif self.thread.getName() == "Warm":
              # unicode char for arrow up
              threadStatus += u'\u2191'
          else:
            self.thread = None

        self.cameraTemp.set(f"Temp: {self.camera.temperature:.1f} C {threadStatus}")      
        self.cameraCooler.set(f"Cooler: {'On' if self.camera.cooler == True else 'Off'} power: {self.camera.coolerpower}")

      else:
        # unicode char for not connected
        self.cameraTemp.set(u'')
        self.cameraCooler.set("Cooler: \u1f50c")

    except Exception as ex:
      print(f"Failed to update camera status: {ex}")
      # unicode char for failure
      self.cameraTemp.set('')
      self.cameraCooler.set("Cooler: \u26A0")
