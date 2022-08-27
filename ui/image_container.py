import time
import tkinter as tk
import tkinter.ttk as ttk
import rawpy
from PIL import ImageTk
from astropy.io import fits
import cv2
import numpy as np
from debayer.bilinear import debayer_bilinear
from debayer.superpixel import debayer_superpixel

from snap_process import ImageData

class ImageViewer:

  def __init__(self, parentFrame):
    self.scaledImg = None
    self.imageScale = 1.0

    # Image container
    self.imageCanvas = tk.Canvas(parentFrame, background="#200")
    self.image_container = None
    hbar=ttk.Scrollbar(parentFrame, orient=tk.HORIZONTAL)
    hbar.pack(side=tk.BOTTOM, fill=tk.X)
    hbar.config(command=self.imageCanvas.xview)
    vbar=ttk.Scrollbar(parentFrame, orient=tk.VERTICAL)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    vbar.config(command=self.imageCanvas.yview)
    self.imageCanvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
    self.imageCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

    # Zoom buttons
    zoomControl = ttk.Frame(parentFrame)
    ttk.Button(zoomControl, text="+", command=self.zoomin, style='X.TButton', width=2).pack(side=tk.RIGHT)
    ttk.Button(zoomControl, text="-", command=self.zoomout, style='X.TButton', width=2).pack(side=tk.RIGHT)
    zoomControl.place(x=5, y=5)

  def update(self):
    if self.scaledImg is not None:
      ppm_header = f'P6 {self.scaledImg.shape[1]} {self.scaledImg.shape[0]} 255 '.encode()
      data = ppm_header + self.scaledImg.tobytes()
      self.imageObject = ImageTk.PhotoImage(width=self.scaledImg.shape[1], height=self.scaledImg.shape[0], data=data, format='PPM')
      if self.image_container is None:
          self.image_container = self.imageCanvas.create_image((0,0), image=self.imageObject, anchor='nw')
      else:
          self.imageCanvas.itemconfig(self.image_container, image=self.imageObject)

  def zoomin(self):
      self.imageScale += 0.5
      self.update()
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

  def zoomout(self):
      self.imageScale -= 0.5
      self.update()
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

  def setImage(self, imgData: ImageData):
    start_time = time.time_ns()
    if imgData.image is None:
        ext = imgData.fname[-3:].lower()
        if ext == 'nef':
            raw = rawpy.imread(imgData.fname)
            print(f"Postprocessing {imgData.fname}")
            params = rawpy.Params(demosaic_algorithm = rawpy.DemosaicAlgorithm.AHD,
                half_size = False,
                four_color_rgb = False,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                use_camera_wb=True,
                use_auto_wb=False,
                #output_color=rawpy.ColorSpace.raw, 
                #output_bps = 8,
                user_flip = 0,
                no_auto_scale = False,
                no_auto_bright=True
                #highlight_mode= rawpy.HighlightMode.Clip
                )

            end_load_time = time.time_ns()

            img = raw.postprocess(params=params)
            raw.close()

        elif ext == 'fit':
            f = fits.open(imgData.fname)
            ph = f[0]
            img = ph.data

            end_load_time = time.time_ns()
            load_time = end_load_time - start_time

            if ph.header['BAYERPAT'] == 'RGGB':
                deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2RGB)
                img = deb.astype(np.float32) / np.iinfo(deb.dtype).max
                img = (img * 255).astype(np.uint8)
            else:
                raise NotImplementedError(f"Unsupported bayer pattern: {ph.header['BAYERPAT']}")
    else:
        if imgData.image is not None:
            img = imgData.image
            end_load_time = start_time
            load_time = 0
            if imgData.header['BAYERPAT'] == 'RGGB':
                img = debayer_superpixel(img)
                # deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2RGB_EA)
                # img = deb.astype(np.float32) * (255.0 / np.iinfo(deb.dtype).max)
                # img = img.astype(np.uint8)
            else:
                raise NotImplementedError(f"Unsupported bayer pattern: {imgData.header['BAYERPAT']}")
            deb_finish_time = time.time_ns()
            deb_time = deb_finish_time - end_load_time

    scale_start_time = deb_finish_time
    imgCanvasWidth, imgCanvasHeight = self.imageCanvas.winfo_width(), self.imageCanvas.winfo_height()
    imgAspect = img.shape[0] / img.shape[1]

    if imgCanvasWidth * imgAspect <= imgCanvasHeight:
        w = imgCanvasWidth
        h = int(imgCanvasWidth * imgAspect)
    else:
        h = imgCanvasHeight
        w = int(imgCanvasHeight / imgAspect)

    self.scaledImg = cv2.resize(img, dsize=(int(w*self.imageScale), int(h*self.imageScale)), interpolation=cv2.INTER_LINEAR)

    scale_end_time = time.time_ns()
    scale_time = scale_end_time - scale_start_time
    print(f"load_time: {load_time/1e9:0.3f}, deb_time: {deb_time/1e9:0.3f}, scale_time: {scale_time/1e9:0.3f}")

    self.update()
    return img

  def onResize(self):
    self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
    self.update()
