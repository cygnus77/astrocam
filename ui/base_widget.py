import tkinter as tk
import tkinter.ttk as ttk

class BaseWidget:
  EntryFont = ("Segoe UI", 14)
  EntryWidth = 5

  GREEN_CHECK = u'\u2713'
  EXCLAMATION = u'\u2757'
  STOP = u'\u25CF'
  UNPLUGGED = 'Disconnected'

  def __init__(self, parentFrame, widgetName):
    self.widgetName = widgetName
    self.status = self.UNPLUGGED

    self.headervar = tk.StringVar()
    self.widgetFrame = ttk.Frame(parentFrame)
    self.widgetFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    frame_label = ttk.Label(self.widgetFrame, textvariable=self.headervar)
    frame_label.pack()
    self.setHeader()

  def setHeader(self, text=""):
    self.headervar.set(f"{self.widgetName} ({self.status}) {text}")

  def update(self):
    try:
      if self._update():
        self.headervar.set(f"{self.widgetName}: {self.GREEN_CHECK}")
      else:
        self.headervar.set(f"{self.widgetName}: {self.UNPLUGGED}")
    except Exception as ex:
      self.headervar.set(f"{self.widgetName}: {self.EXCLAMATION}")

  def connect(self, device):
    try:
      self._connect(device)
    except Exception as ex:
      print(f"Failed to connect to {self.widgetName}: {ex}")

  def disconnect(self):
    try:
      self._disconnect()
    except Exception as ex:
      print(f"Failed to disconnect from {self.widgetName}: {ex}")
