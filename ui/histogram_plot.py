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


class RGBHistogramSlider(tk.Canvas):
  def __init__(self, parent, width=300, height=50, min_val=0, max_val=255, init_low=0, init_high=255, **kwargs):
    super().__init__(parent, width=width, height=height, background="#200", highlightbackground="#200", highlightthickness=0, **kwargs)
    self.min_val = min_val
    self.max_val = max_val
    self.width = width
    self.height = height
    self.low_val = [init_low, init_low, init_low]
    self.high_val = [init_high, init_high, init_high]
    self.padding = 10

    self.right_marker = (0, 0, 9, 5, 0, 9, 0, 0)
    self.left_marker = (9, 0, 9, 9, 0, 5, 9, 0)
    self.low_marker = [self.create_polygon(*self.right_marker, fill=col, outline=col) for col in ['red', 'green', 'blue']]
    self.high_marker = [self.create_polygon(*self.left_marker, fill=col, outline=col) for col in ['red', 'green', 'blue']]
    self.marker_offsets = [10, 25, 40]
    self.range_line = [
      self.create_line(0, 0, 0, 0, fill=col, width=2) for col in ['red', 'green', 'blue']
    ]

    self.bind("<B1-Motion>", self._on_drag)
    self.bind("<Button-1>", self._on_click)
    self._update_positions()

  def _update_positions(self):
    for i in range(3):
      low_x = self._value_to_x(self.low_val[i])
      high_x = self._value_to_x(self.high_val[i])
      offset_y = self.marker_offsets[i]
      
      translated_right_marker = []
      translated_left_marker = []
      for j in range(0, len(self.right_marker), 2):
        translated_right_marker.append(self.right_marker[j] + low_x)
        translated_right_marker.append(self.right_marker[j+1] + offset_y - 5)
        translated_left_marker.append(self.left_marker[j] + high_x - 1)
        translated_left_marker.append(self.left_marker[j+1] + offset_y - 5)

      self.coords(self.low_marker[i], *translated_right_marker)
      self.coords(self.high_marker[i], *translated_left_marker)
      self.coords(self.range_line[i],
        self._value_to_x(self.low_val[i]), self.marker_offsets[i], 
        self._value_to_x(self.high_val[i]), self.marker_offsets[i])

  def _value_to_x(self, value):
    return self.padding + (value - self.min_val) / (self.max_val - self.min_val) * (self.width - 2 * self.padding)

  def _x_to_value(self, x):
    return self.min_val + (x - self.padding) / (self.width - 2 * self.padding) * (self.max_val - self.min_val)

  def _on_drag(self, event):
    x = max(self.padding, min(event.x, self.width - self.padding))
    value = int(self._x_to_value(x))
    for i in range(3):
      offset_y = self.marker_offsets[i]
      if abs(event.y - offset_y) <= 5:
        if abs(x - self._value_to_x(self.low_val[i])) < abs(x - self._value_to_x(self.high_val[i])):
          self.low_val[i] = max(self.min_val, min(value, self.high_val[i]))
        else:
          self.high_val[i] = min(self.max_val, max(value, self.low_val[i]))
        break
    self._update_positions()
    self.event_generate("<<RangeChanged>>")

  def _on_click(self, event):
    self._on_drag(event)


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

    self.lock_button = tk.Button(button_frame, text="🔓", command=self._toggle_lock, bg="#200", fg="white", relief=tk.FLAT)
    self.lock_button.pack(side=tk.LEFT, padx=5)
    self.locked = False

    self.auto_button = tk.Button(button_frame, text="⚡", command=self._toggle_auto, bg="#200", fg="white", relief=tk.FLAT)
    self.auto_button.pack(side=tk.LEFT, padx=5)
    self.auto_stretch = True

    self.range_slider = RGBHistogramSlider(frame, width=width)
    self.range_slider.pack(side=tk.TOP, fill=tk.X)
    self.range_slider.bind("<<RangeChanged>>", self.slider_changed)

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

  def _toggle_auto(self):
    self.auto_stretch = not self.auto_stretch
    self.auto_button.config(text="⚡️" if self.auto_stretch else "🛠️")
    if self.auto_stretch:
      self._stretch()

  def _toggle_lock(self):
    self.locked = not self.locked
    self.lock_button.config(text="🔒" if self.locked else "🔓")

  def slider_changed(self, evt):
    if self.locked:
      self.image_container.stretch(self.range_slider.low_val[0], self.range_slider.high_val[0])
    else:
      self.image_container.stretch(self.range_slider.low_val, self.range_slider.high_val)

  def _stretch(self):
    if self.red is None or self.green is None or self.blue is None:
      return
    try:
      a = []
      b = []
      for i, h in enumerate([self.red, self.green, self.blue]):
          fit_g = fit_1dgausssian(h)
          if fit_g is None:
            raise ValueError("Gaussian fit error")
          ampl, avg, stddev = fit_g
          fwhm = abs(8 * np.log(2) * stddev)
          a.append(max(int(avg - 2 * fwhm), 0))
          b.append(min(int(avg + 20 * fwhm), 255))
      self.image_container.stretch(a, b)

      self.range_slider.low_val = [int(a) for a in a]
      self.range_slider.high_val = [int(b) for b in b]
      self.range_slider._update_positions()
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
  ctrl = HistogramViewer(mainFrame)
  img = ImageData(None, fname=r"D:\Astro\20230319-M81M82_M101_M13\Light-M101-300sec\Light_ASIImg_300sec_Bin1_-9.4C_gain200_2023-03-20_023749_frame0026.fit", header={})
  ctrl.update(img)
  mainFrame.pack()
  root.mainloop()
