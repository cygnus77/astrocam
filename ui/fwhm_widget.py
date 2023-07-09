from datetime import datetime
import tkinter as tk
import tkinter.ttk as ttk
import numpy as np
from fwhm.star_finder import StarFinder
from fwhm.star_matcher import StarMatcher
from ui.base_widget import BaseWidget
import pandas as pd
import cv2
import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class FWHMWidget(BaseWidget):

  def __init__(self, parentFrame):
    super().__init__(parentFrame, "FWHM")
    self.starFinder = StarFinder()
    self.starMatcher = StarMatcher()

    # Canvas for fwhm plot
    tk_canvas = tk.Canvas(self.widgetFrame, width=250, height=250, background="#200")
    tk_canvas.pack()

    self.fig = Figure(figsize=(2.5, 2.5), dpi=100)
    self.fig.set_facecolor("#200")
    self.ax = self.fig.add_subplot(111)
    self.ax.set_facecolor("#200")
    self.ax.tick_params(axis='x', colors='white')
    self.ax.tick_params(axis='y', colors='white')
    self.ax2 = self.ax.twinx()
    self.ax2.tick_params(axis='y', colors='white')
    
    self.canvas = FigureCanvasTkAgg(self.fig, master=tk_canvas)
    self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    # Reset button
    ttk.Button(self.widgetFrame, text="Reset", command=self.reset).pack(fill=tk.X, side=tk.TOP)

    self.reset()

  def _connect(self, camera):
    self.reset()
    return

  def _disconnect(self):
    return

  def reset(self):
    self.fwhm_data = []
    self.stars = []
    self.targetStar = []
    self.render_fwhm_plot()

  def _update(self, img16: np.ndarray):
    assert(img16.dtype == np.uint16)
    assert(len(img16.shape) == 3)
    assert(img16.shape[2] == 3)
    img16 = cv2.cvtColor(img16, cv2.COLOR_RGB2GRAY)
    img8 = ((img16 / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)
    numStars = 20
    star_img, df = self.starFinder.find_stars(img8=np.squeeze(img8), img16=np.squeeze(img16), topk=numStars)
    fwhm = {
      "numstars": len(df),
      "fwhm_x": df.fwhm_x.mean(),
      "fwhm_y":df.fwhm_y.mean(),
      "fwhm_ave":((df.fwhm_x + df.fwhm_y)/2).mean()}
    self.fwhm_data.append(fwhm)
    self.render_fwhm_plot()
    self.stars = df

    if self.targetStar:
      s =  self.targetStar[-1][1]
      y = df[(abs(df.cluster_cx - s.cluster_cx) < 5) & (abs(df.cluster_cy - s.cluster_cy) < 5)]
      if len(y):
        self.targetStar.append((len(self.fwhm_data), y.iloc[0]))

    return True

  def setTargetStar(self, star):
    self.targetStar = [(len(self.fwhm_data), star)]

  def render_fwhm_plot(self):
    self.ax.clear()
    self.ax2.clear()
    if len(self.fwhm_data) == 0:
      self.canvas.draw()
      return
    # self.ax.plot([x['fwhm_x'] for x in self.fwhm_data], label="x")
    # self.ax.plot([x['fwhm_y'] for x in self.fwhm_data], label="y")
    y = np.array([x['fwhm_ave'] for x in self.fwhm_data])
    x = np.arange(len(self.fwhm_data))
    self.ax.plot(y, label="ave")
    if self.targetStar:
      self.ax.plot([x[0] for x in self.targetStar], [(x[1].fwhm_x + x[1].fwhm_y)/2 for x in self.targetStar], label='target')

    # Star count
    self.ax2.plot([x['numstars'] for x in self.fwhm_data], 'g--', label="n")

    # Trend line
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    self.ax.plot(x, p(x))
    self.fig.legend(loc='upper left')
    self.canvas.draw()
    self.hdrInfo.set(f"{y[-1]:.2f} px")
