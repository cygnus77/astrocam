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

    # Create widget super frame
    self.hdrFrame = ttk.Frame(parentFrame)
    self.hdrFrame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    self.hdrInfo = tk.StringVar()
    frame_label = ttk.Label(self.hdrFrame, textvariable=self.hdrInfo)
    frame_label.pack(side=tk.RIGHT, expand=True)

    self.hdrConnStat = tk.StringVar()
    frame_label = ttk.Label(self.hdrFrame, textvariable=self.hdrConnStat)
    frame_label.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Create the collapse/expand label
    self.collapse_icon = ttk.Label(self.hdrFrame, text=u'\u25B6', font=('Arial', 10, 'bold'))
    self.collapse_icon.pack(side=tk.LEFT, fill=tk.X, expand=False)
    self.collapse_icon.bind('<Button-1>', lambda e: self.toggle_frame())
    self.updateHeader()

    self.widgetFrame = ttk.Frame(parentFrame)
    self.widgetFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    self.widgetFrame.pack_forget()

  def updateHeader(self):
    self.hdrConnStat.set(f"{self.widgetName}: {self.status}")

  def update(self, *args, **kwargs):
    try:
      if self._update(*args, **kwargs):
        self.status = self.GREEN_CHECK
      else:
        self.status = self.UNPLUGGED
        self.hdrInfo.set("")
    except Exception as ex:
      print(f"Failed to update {self.widgetName}: {ex}")
      self.status = self.EXCLAMATION
      self.hdrInfo.set("")
    self.updateHeader()

  def connect(self, device):
    try:
      self._connect(device)
      self.status = self.GREEN_CHECK
    except Exception as ex:
      print(f"Failed to connect to {self.widgetName}: {ex}")
      self.status = self.EXCLAMATION
      self.hdrInfo.set("")
    self.updateHeader()

  def disconnect(self):
    try:
      self._disconnect()
      self.status = self.UNPLUGGED
    except Exception as ex:
      print(f"Failed to disconnect from {self.widgetName}: {ex}")
      self.status = self.EXCLAMATION
    self.hdrInfo.set("")
    self.updateHeader()

  def toggle_frame(self):
    if self.widgetFrame.winfo_viewable():
      self.widgetFrame.pack_forget()
      self.collapse_icon.config(text=u'\u25B6')  # Unicode character for right-pointing triangle
    else:
      self.widgetFrame.pack()
      self.collapse_icon.config(text=u'\u25BC')  # Unicode character for black down-pointing triangle
