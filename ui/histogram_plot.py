import tkinter as tk
import tkinter.ttk as ttk
from PIL import ImageTk, Image
import numpy as np
import time
import cv2

class HistogramViewer:

  def __init__(self, parentFrame):
    self.histoCanvas=tk.Canvas(parentFrame, bg='black')
    self.histoCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
    self.histImg = None

  def setImage(self, img: np.ndarray):
    start_time = time.time_ns()
    red = np.bincount(img[:,:,0].reshape(-1), minlength=256)
    green = np.bincount(img[:,:,1].reshape(-1), minlength=256)
    blue = np.bincount(img[:,:,2].reshape(-1), minlength=256)

    def make_layer(a):
      ht = 256
      wd = 256
      a = a * ht / a.max()
      a = a.astype(np.uint32)
      layer = np.zeros((ht, wd), dtype=np.uint8)
      for i in range(wd):
        layer[ht-a[i]:ht, i] = 255
      return layer

    r_layer = make_layer(red)
    g_layer = make_layer(green)
    b_layer = make_layer(blue)
    histImg = np.stack([r_layer, g_layer, b_layer],axis=2)

    imgCanvasWidth, imgCanvasHeight = self.histoCanvas.winfo_width(), self.histoCanvas.winfo_height()
    imgAspect = img.shape[0] / img.shape[1]

    if imgCanvasWidth * imgAspect <= imgCanvasHeight:
        w = imgCanvasWidth
        h = int(imgCanvasWidth * imgAspect)
    else:
        h = imgCanvasHeight
        w = int(imgCanvasHeight / imgAspect)

    self.histImg = cv2.resize(histImg, dsize=(int(w), int(h)), interpolation=cv2.INTER_LINEAR)
    self.update()

    histo_time = time.time_ns() - start_time
    print(f"histo_time: {histo_time/1e9:0.3f}")
    

  def update(self):
    if self.histImg is not None:
      self.histImgObject = ImageTk.PhotoImage(image=Image.fromarray(self.histImg))
      self.histoCanvas.create_image(0, 0, image = self.histImgObject, anchor = tk.NW)

