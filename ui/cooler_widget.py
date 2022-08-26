import tkinter as tk
import tkinter.ttk as ttk

from threading import Thread
from base_widget import BaseWidget


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

  def coolCamera(self):
    thread = Thread(target=self.camera.coolto, args=[0])
    thread.start()

  def warmCamera(self):
    thread = Thread(target=self.camera.warmto, args=[25])
    thread.start()

  def update(self):
    self.cameraTemp.set(f"Temp: {self.camera.temperature:.1f} C")
    self.cameraCooler.set(f"Cooler: {'On' if self.camera.cooler == True else 'Off'} power: {self.camera.coolerpower}")
