import traceback
import tkinter as tk
import tkinter.ttk as ttk
from app import AstroApp
from ui.cooler_widget import CoolerWidget
from argparse import ArgumentParser
import psutil
import sys

from ui.equipment_selector import make_camera, CAMERA_CHOICES

class CoolerApp(AstroApp):
  def __init__(self, camera_name):
    super().__init__()
    self.root.geometry("500x200")
    self.camera = make_camera(camera_name)

    # Layout
    paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
    paned_window.pack(fill=tk.BOTH, expand=True)

    coolerFrame = ttk.Frame(paned_window)
    self.coolerWidget = CoolerWidget(coolerFrame, self.camera)
    coolerFrame.pack(fill=tk.X, side=tk.TOP)
    paned_window.add(coolerFrame, weight=1)
    self.coolerWidget.connect(self.camera)
    self.root.after(1000, self.statusPolling)

  def statusPolling(self):
    self.coolerWidget.update()
    self.root.after(1000, self.statusPolling)

if __name__ == "__main__":
  ap = ArgumentParser()
  ap.add_argument('camera', choices=CAMERA_CHOICES)
  args = ap.parse_args()

  def isCoolerProc(p):
    try:
      if "python.exe" in p.name():
        cmdline = ' '.join(p.cmdline())
        if "coolerapp.py " in cmdline and args.camera in cmdline:
          return True
    except:
      return False

  exact_matches = [p for p in psutil.process_iter() if isCoolerProc(p)]
  if len(exact_matches) == 1:
    coolerapp = CoolerApp(args.camera)
    coolerapp.root.mainloop()
