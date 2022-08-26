import tkinter as tk
import tkinter.ttk as ttk
import numpy as np
import time

class HistogramViewer:

  def __init__(self, parentFrame, width, height):
    self.width = width
    self.height = height
    self.histoCanvas=tk.Canvas(parentFrame, width=self.width, height=self.height, bg='black')
    self.histoCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
    self.histo_lines = None
    self.histoCanvas.create_rectangle( (0, 0, self.width, self.height), fill="black")
    self.histoData = None
    self.histo_lines = None

  def onResize(self):
    self.update()

  def setImage(self, img: np.ndarray):
    start_time = time.time_ns()
    red = np.bincount(img[:,:,0].reshape(-1), minlength=256)
    green = np.bincount(img[:,:,1].reshape(-1), minlength=256)
    blue = np.bincount(img[:,:,2].reshape(-1), minlength=256)
    sf_y = self.height / np.max([red, green, blue])
    sf_x = self.width / 256

    self.red_pts = []
    self.green_pts = []
    self.blue_pts = []
    for i in range(len(red)):
        self.red_pts.append(int(i*sf_x))
        self.red_pts.append(self.height-round(red[i] * sf_y))
        self.green_pts.append(int(i*sf_x))
        self.green_pts.append(self.height-round(green[i] * sf_y))
        self.blue_pts.append(int(i*sf_x))
        self.blue_pts.append(self.height-round(blue[i] * sf_y))

    histo_time = time.time_ns() - start_time
    print(f"histo_time: {histo_time/1e9:0.3f}")

  def update(self):
    if self.histoData is not None:
        if self.histo_lines is None:
          self.histo_lines = [self.histoCanvas.create_line(pts, fill=color)
            for pts, color in zip(
                [self.red_pts, self.green_pts, self.blue_pts],
                ['red', 'lightgreen, white']
            )]
        else:
            for lines, data in zip(self.histo_lines, [self.red_pts, self.green_pts, self.blue_pts]):
                self.histoCanvas.coords(lines, data)

