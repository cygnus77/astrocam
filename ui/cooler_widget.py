import tkinter as tk
import tkinter.ttk as ttk

from threading import Thread
from ui.base_widget import BaseWidget


class CoolerWidget(BaseWidget):
  def __init__(self, parentFrame, device):
    super().__init__(parentFrame, "Cooler", collapsed=False)
    self.camera = device

    self.cameraTemp = tk.StringVar()
    # self.cameraCooler = tk.StringVar()
    self.targetCoolTemp = tk.DoubleVar(value=0.0)
    self.targetWarmTemp = tk.DoubleVar(value=25.0)

    tempFrame = ttk.Frame(self.widgetFrame)
    
    # First row: [ [targettemp, label ], button ]
    coolFrame = ttk.Frame(tempFrame)
    targetCoolFrame = ttk.Frame(coolFrame)
    ttk.Entry(targetCoolFrame, textvariable=self.targetCoolTemp, width=10, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Label(targetCoolFrame, text="°C").pack(side=tk.LEFT, padx=5, pady=5)
    targetCoolFrame.pack(side=tk.TOP, fill=tk.X)
    ttk.Button(coolFrame, text="Cool", command=self.coolCamera).pack(side=tk.BOTTOM, padx=5, pady=5, fill=tk.X)
    coolFrame.pack(side=tk.LEFT, fill=tk.X)
    
    ttk.Separator(tempFrame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

    # Second row: [ cameraTemp ]
    ttk.Label(tempFrame, textvariable=self.cameraTemp, font=("Helvetica", 16)).pack(side=tk.LEFT, padx=5, pady=5)
    
    ttk.Separator(tempFrame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

    # Third row: [ [targettemp, label ], button ]
    warmFrame = ttk.Frame(tempFrame)
    targetWarmFrame = ttk.Frame(warmFrame)
    ttk.Entry(targetWarmFrame, textvariable=self.targetWarmTemp, width=10, font=("Helvetica", 12)).pack(side=tk.LEFT, padx=5, pady=5)
    ttk.Label(targetWarmFrame, text="°C").pack(side=tk.LEFT, padx=5, pady=5)
    targetWarmFrame.pack(side=tk.TOP, fill=tk.X)
    ttk.Button(warmFrame, text="Warm", command=self.warmCamera).pack(side=tk.BOTTOM, padx=5, pady=5, fill=tk.X)
    warmFrame.pack(side=tk.LEFT, fill=tk.X)


    tempFrame.pack(fill=tk.X, side=tk.TOP)
    # Cooler & power status
    # coolerFrame = ttk.Frame(self.widgetFrame)
    # ttk.Label(coolerFrame, textvariable=self.cameraCooler).pack(side=tk.LEFT, padx=5, pady=5)
    # coolerFrame.pack(fill=tk.X, side=tk.TOP)

    self.thread = None

  def _connect(self, camera):
    self.camera = camera

  def _disconnect(self):
    self.camera = None

  def coolCamera(self):
    self.thread = Thread(target=self.camera.coolto, args=[self.targetCoolTemp.get()], name="Cool")
    self.thread.start()

  def warmCamera(self):
    self.thread = Thread(target=self.camera.warmto, args=[25], name="Warm")
    self.thread.start()

  def _update(self):
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

      stat = 'On' if self.camera.cooler == True else 'Off'
      temperature = self.camera.temperature
      coolerpower = self.camera.coolerpower
      self.cameraTemp.set(f"({stat} {coolerpower}%) {threadStatus}")
      self.hdrInfo.set(f"{stat} {temperature:.1f} C")
      return True
    return False

