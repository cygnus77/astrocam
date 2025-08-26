import tkinter as tk
import tkinter.ttk as ttk
from PIL import ImageTk, Image
import numpy as np
import time
import cv2
from image_data import ImageData
from ui.base_widget import BaseWidget
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
from fwhm.fwhm import fit_1dgausssian


class HistogramViewer(BaseWidget):

  def __init__(self, parentFrame, image_container):
    super().__init__(parentFrame, "Histogram")
    self.image_container = image_container

    width = 350
    frame = ttk.Frame(self.widgetFrame)
    self.histoCanvas=tk.Canvas(frame, width=width, height=250, background="#200")
    self.histoCanvas.pack(side=tk.TOP)

    button_frame = ttk.Frame(frame)
    button_frame.pack(side=tk.TOP, fill=tk.X)

    self.lock_button = tk.Button(button_frame, text="🔓", command=self._slider_toggle_lock, bg="#200", fg="white", relief=tk.FLAT)
    self.lock_button.pack(side=tk.LEFT, padx=5)
    self.locked = False

    self.auto_button = tk.Button(button_frame, text="⚡", command=self._slider_toggle_auto, bg="#200", fg="white", relief=tk.FLAT)
    self.auto_button.pack(side=tk.LEFT, padx=5)
    self.auto_stretch = True

    self.range_slider = tk.Canvas(frame, width=300, height=50, background="#200", highlightbackground="#200", highlightthickness=0) # RGBHistogramSlider(frame, width=width)
    self.range_slider.pack(side=tk.TOP, fill=tk.X)
    self.slider_right_marker = (0, 0, 9, 5, 0, 9, 0, 0)
    self.slider_left_marker = (9, 0, 9, 9, 0, 5, 9, 0)
    self.slider_low_marker = [self.range_slider.create_polygon(*self.slider_right_marker, fill=col, outline=col) for col in ['red', 'green', 'blue']]
    self.slider_high_marker = [self.range_slider.create_polygon(*self.slider_left_marker, fill=col, outline=col) for col in ['red', 'green', 'blue']]
    self.slider_marker_offsets = [10, 25, 40]
    self.slider_range_lines = [
      self.range_slider.create_line(0, 0, 0, 0, fill=col, width=2) for col in ['red', 'green', 'blue']
    ]
    self.range_slider.bind("<B1-Motion>", self._slider_on_drag)
    self.range_slider.bind("<Button-1>", self._on_slider_click)
    self.slider_width = 300
    self.slider_min_val = 0
    self.slider_max_val = 255
    self.slider_low_val = [0, 0, 0]
    self.slider_high_val = [255, 255, 255]
    self.slider_padding = 10

    frame.pack(side=tk.TOP)

    fig = Figure(figsize=(width/72, 2.5), dpi=72)
    fig.set_facecolor("#200")
    self.ax = fig.add_axes([0, 0, 1, 1])  # Make the axis fill the entire figure
    self.ax.set_facecolor("#200")
    self.ax.tick_params(axis='x', colors='white')
    self.ax.tick_params(axis='y', colors='white')

    x = np.linspace(0, 255, 5)
    self.ax.set_xticks(x)
    self.ax.set_xticklabels([f'{int(tick)}' for tick in x])

    self.canvas = FigureCanvasTkAgg(fig, master=self.histoCanvas)
    self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    self.red = None
    self.green = None
    self.blue = None

    self._update_slider_positions()

  def _update_slider_positions(self):
    for i in range(3):
      low_x = self._slider_value_to_x(self.slider_low_val[i])
      high_x = self._slider_value_to_x(self.slider_high_val[i])
      offset_y = self.slider_marker_offsets[i]
      
      translated_right_marker = []
      translated_left_marker = []
      for j in range(0, len(self.slider_right_marker), 2):
        translated_right_marker.append(self.slider_right_marker[j] + low_x)
        translated_right_marker.append(self.slider_right_marker[j+1] + offset_y - 5)
        translated_left_marker.append(self.slider_left_marker[j] + high_x - 1)
        translated_left_marker.append(self.slider_left_marker[j+1] + offset_y - 5)

      self.range_slider.coords(self.slider_low_marker[i], *translated_right_marker)
      self.range_slider.coords(self.slider_high_marker[i], *translated_left_marker)
      self.range_slider.coords(self.slider_range_lines[i],
        self._slider_value_to_x(self.slider_low_val[i]), self.slider_marker_offsets[i], 
        self._slider_value_to_x(self.slider_high_val[i]), self.slider_marker_offsets[i])

  def _slider_value_to_x(self, value):
    return self.slider_padding + (value - self.slider_min_val) / (self.slider_max_val - self.slider_min_val) * (self.slider_width - 2 * self.slider_padding)

  def _slider_x_to_value(self, x):
    return self.slider_min_val + (x - self.slider_padding) / (self.slider_width - 2 * self.slider_padding) * (self.slider_max_val - self.slider_min_val)

  def _slider_on_drag(self, event):
    x = max(self.slider_padding, min(event.x, self.slider_width - self.slider_padding))
    value = int(self._slider_x_to_value(x))
    for i in range(3):
      offset_y = self.slider_marker_offsets[i]
      if abs(event.y - offset_y) <= 5:
        if abs(x - self._slider_value_to_x(self.slider_low_val[i])) < abs(x - self._slider_value_to_x(self.slider_high_val[i])):
          self.slider_low_val[i] = max(self.slider_min_val, min(value, self.slider_high_val[i]))
        else:
          self.slider_high_val[i] = min(self.slider_max_val, max(value, self.slider_low_val[i]))
        if self.locked:
          for k in range(3):
            if k != i:
              self.slider_low_val[k] = self.slider_low_val[i]
              self.slider_high_val[k] = self.slider_high_val[i]
        break
    self.auto_stretch = False
    self.auto_button.config(text="🛠️")
    self._update_slider_positions()
    self._slider_changed()

  def _on_slider_click(self, event):
    self._slider_on_drag(event)

  def _slider_toggle_auto(self):
    self.auto_stretch = not self.auto_stretch
    self.auto_button.config(text="⚡️" if self.auto_stretch else "🛠️")
    if self.auto_stretch:
      self._stretch()
      self.image_container.refresh()

  def _slider_toggle_lock(self):
    self.locked = not self.locked
    self.lock_button.config(text="🔒" if self.locked else "🔓")
    if self.locked:
      for k in range(1,3):
        self.slider_low_val[k] = self.slider_low_val[0]
        self.slider_high_val[k] = self.slider_high_val[0]
      self._update_slider_positions()
      self._slider_changed()

  def _slider_changed(self):
    if self.locked:
      self.image_container.set_stretch(self.slider_low_val[0], self.slider_high_val[0])
    else:
      self.image_container.set_stretch(self.slider_low_val, self.slider_high_val)
    self.image_container.refresh()

  def _stretch(self):
    if self.red is None or self.green is None or self.blue is None:
      return
    try:
      a = []
      b = []
      for i, h in enumerate([self.red, self.green, self.blue]):
          fit_g = fit_1dgausssian(h)[:3]
          if fit_g is None:
            raise ValueError("Gaussian fit error")
          ampl, avg, stddev = fit_g
          fwhm = abs(8 * np.log(2) * stddev)
          a.append(max(int(avg - 1.0 * fwhm), 1))
          b.append(min(int(avg + 2.5 * fwhm), 255))
      self.image_container.set_stretch(a, b)

      self.slider_low_val = [int(a) for a in a]
      self.slider_high_val = [int(b) for b in b]
      self._update_slider_positions()
    except ValueError as err:
      print(err)
      pass

  def _update(self, img: ImageData):
    if img is None:
      return

    if True:
      img = img.deb16
      self.red, _ = np.histogram(img[:,:,0], bins=256, range=(0, 65536))
      self.green, _ = np.histogram(img[:,:,1], bins=256, range=(0, 65536))
      self.blue, _ = np.histogram(img[:,:,2], bins=256, range=(0, 65536))
    else:
      img = img.rgb24
      self.red = np.bincount(img[:,:,0].reshape(-1))
      self.green = np.bincount(img[:,:,1].reshape(-1))
      self.blue = np.bincount(img[:,:,2].reshape(-1))

    m = np.max([np.max(self.red), np.max(self.blue), np.max(self.green)])
    # m = 1e3 * int((m + 1e3)/1e3)
    y = np.linspace(0, m, 5)
    self.ax.clear()
    self.ax.set_yticks(y)
    self.ax.set_yticklabels([])
    self.ax.plot(self.red, 'r')
    self.ax.plot(self.green, 'g')
    self.ax.plot(self.blue, 'b')

    if self.auto_stretch:
      self._stretch()
  
    self.canvas.draw()


if __name__ == "__main__":
  root = tk.Tk()
  mainFrame = ttk.Frame(root)
  ctrl = HistogramViewer(mainFrame, None)
  img = ImageData(None, fname=r"C:\code\astrocam\images\20250825\M 57 NGC 6720\Light\Light_00793_10.0sec_200gain_0.0C.fit", header={})
  ctrl.update(img)
  mainFrame.pack()
  root.mainloop()
