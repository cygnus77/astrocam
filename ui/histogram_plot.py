import tkinter as tk
import tkinter.ttk as ttk
from PIL import ImageTk, Image
import numpy as np
import time
import cv2
from ui.base_widget import BaseWidget
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker


class HistogramViewer(BaseWidget):

  def __init__(self, parentFrame):
    super().__init__(parentFrame, "Histogram")
    self.histoCanvas=tk.Canvas(self.widgetFrame, width=300, height=250, background="#200")
    self.histoCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
    self.histImg = None

    fig = Figure(figsize=(3.0, 2.5), dpi=100)
    fig.set_facecolor("#200")
    self.ax = fig.add_subplot(111)
    self.ax.set_facecolor("#200")
    self.ax.tick_params(axis='x', colors='white')
    self.ax.tick_params(axis='y', colors='white')

    self.canvas = FigureCanvasTkAgg(fig, master=self.histoCanvas)
    self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

  def _update(self, img: np.ndarray):
    if img is None:
      return
    red = np.bincount(img[:,:,0].reshape(-1))
    green = np.bincount(img[:,:,1].reshape(-1))
    blue = np.bincount(img[:,:,2].reshape(-1))

    x = np.linspace(0, 65535, 5)
    self.ax.set_xticks(x)
    self.ax.set_xticklabels(['{:.1f}k'.format(tick/1e3) for tick in x])

    m = np.max([np.max(red), np.max(blue), np.max(green)])
    m = 1e3 * int((m + 1e3)/1e3)
    y = np.linspace(0, m, 5)
    self.ax.set_yticks(y)
    self.ax.set_yticklabels(['{:.1f}k'.format(tick/1e3) for tick in y])

    self.ax.plot(red, 'r')
    self.ax.plot(green, 'g')
    self.ax.plot(blue, 'b')

    self.canvas.draw()
