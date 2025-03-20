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
    self.auto_stretch = True

    frame = ttk.Frame(self.widgetFrame)
    self.histoCanvas=tk.Canvas(frame, width=300, height=250, background="#200")
    self.histoCanvas.pack(side=tk.TOP)
    self.low = tk.IntVar(value=0)
    self.high = tk.IntVar(value=255)
    lowSlider = ttk.Scale(frame, variable=self.low, from_=0, to=255, length=235, orient='horizontal', command=self.slider_changed)
    highSlider = ttk.Scale(frame, variable=self.high, from_=0, to=255, length=235, orient='horizontal', command=self.slider_changed)
    lowSlider.place(x=38, y=0)
    highSlider.place(x=38, y=10)
    frame.pack(side=tk.TOP)

    fig = Figure(figsize=(3.0, 2.5), dpi=100)
    fig.set_facecolor("#200")
    self.ax = fig.add_subplot(111)
    self.ax.set_facecolor("#200")
    self.ax.tick_params(axis='x', colors='white')
    self.ax.tick_params(axis='y', colors='white')

    x = np.linspace(0, 255, 5)
    self.ax.set_xticks(x)
    self.ax.set_xticklabels([f'{int(tick)}' for tick in x])

    self.canvas = FigureCanvasTkAgg(fig, master=self.histoCanvas)
    self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

  def slider_changed(self, evt):
    self.image_container.stretch(self.low.get(), self.high.get())

  def _update(self, img: ImageData):
    if img is None:
      return

    start_time = time.time()
    if True:
      img = img.deb16
      red, _ = np.histogram(img[:,:,0], bins=256, range=(0, 65536))
      green, _ = np.histogram(img[:,:,1], bins=256, range=(0, 65536))
      blue, _ = np.histogram(img[:,:,2], bins=256, range=(0, 65536))
    else:
      img = img.rgb24
      red = np.bincount(img[:,:,0].reshape(-1))
      green = np.bincount(img[:,:,1].reshape(-1))
      blue = np.bincount(img[:,:,2].reshape(-1))
    end_time = time.time()
    print(f"Execution time for histogram calculation: {end_time - start_time:.6f} seconds")

    m = np.max([np.max(red), np.max(blue), np.max(green)])
    # m = 1e3 * int((m + 1e3)/1e3)
    y = np.linspace(0, m, 5)
    self.ax.clear()
    self.ax.set_yticks(y)
    self.ax.set_yticklabels([])
    self.ax.plot(red, 'r')
    self.ax.plot(green, 'g')
    self.ax.plot(blue, 'b')

    if self.auto_stretch:
      try:
        a = []
        b = []
        for i, h in enumerate([red, green, blue]):
            fit_g = fit_1dgausssian(h)
            if fit_g is None:
              raise ValueError("Gaussian fit error")
            ampl, avg, stddev = fit_g
            fwhm = abs(8 * np.log(2) * stddev)
            a.append(max(int(avg - 2 * fwhm), 0))
            b.append(min(int(avg + 20 * fwhm), 255))
        self.image_container.stretch(a, b)

        cols = ['red', 'green', 'blue']
        for i, (avg_a, avg_b) in enumerate(zip(a, b)):
            self.ax.scatter(avg_a, m, color=cols[i], marker='>', s=50)
            self.ax.scatter(avg_b, m, color=cols[i], marker='<', s=50)

      except ValueError as err:
        print(err)
        pass

    self.canvas.draw()


if __name__ == "__main__":
  root = tk.Tk()
  mainFrame = ttk.Frame(root)
  ctrl = HistogramViewer(mainFrame)
  img = ImageData(None, fname=r"D:\Astro\20230319-M81M82_M101_M13\Light-M101-300sec\Light_ASIImg_300sec_Bin1_-9.4C_gain200_2023-03-20_023749_frame0026.fit", header={})
  ctrl.update(img)
  mainFrame.pack()
  root.mainloop()
