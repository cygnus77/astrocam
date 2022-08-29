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
    self.image = None
    self.imageScale = 1.0
    self.highlights = None

    # Image container
    self.imageCanvas = tk.Canvas(parentFrame, background="#200")
    self.image_container = None
    self.crosshairs = None
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

    self.imageCanvas.bind("<Configure>", self.resize)

  def update(self):
    if self.image is not None:
      imgCanvasWidth, imgCanvasHeight = self.imageCanvas.winfo_width(), self.imageCanvas.winfo_height()
      print(imgCanvasWidth, imgCanvasHeight)
      imgAspect = self.image.shape[0] / self.image.shape[1]

      if imgCanvasWidth * imgAspect <= imgCanvasHeight:
        w = imgCanvasWidth
        h = int(imgCanvasWidth * imgAspect)
        self.scaleX = (imgCanvasWidth*self.imageScale) / self.image.shape[1]
        self.scaleY = (imgCanvasWidth*imgAspect*self.imageScale) / self.image.shape[0]
      else:
        h = imgCanvasHeight
        w = int(imgCanvasHeight / imgAspect)
        self.scaleX = ((imgCanvasWidth/imgAspect)*self.imageScale) / self.image.shape[1]
        self.scaleY = (imgCanvasWidth*self.imageScale) / self.image.shape[0]
      
      scaledImg = cv2.resize(self.image, dsize=(int(w*self.imageScale), int(h*self.imageScale)), interpolation=cv2.INTER_LINEAR)
      h, w = scaledImg.shape[:2]

      ppm_header = f'P6 {w} {h} 255 '.encode()
      data = ppm_header + scaledImg.tobytes()
      self.imageObject = ImageTk.PhotoImage(width=w, height=h, data=data, format='PPM')

      c_x, c_y = w//2, h//2
      if self.image_container is None:
        self.image_container = self.imageCanvas.create_image((0,0), image=self.imageObject, anchor='nw')
        self.crosshairs = "crosshairs"
        crosshairs = [
          self.imageCanvas.create_oval(c_x-25, c_y-25, c_x+25, c_y+25, outline="red"),
          self.imageCanvas.create_line(c_x-50, c_y, c_x+50, c_y, fill='red'),
          self.imageCanvas.create_line(c_x, c_y-50, c_x, c_y+50, fill='red'),
        ]
        for item in crosshairs:
          self.imageCanvas.itemconfig(item, tags=(self.crosshairs))
      else:
        self.imageCanvas.itemconfig(self.image_container, image=self.imageObject)
        self.imageCanvas.moveto(self.crosshairs, c_x-25, c_y-25)


  def zoomin(self):
    if self.imageScale < 5:
      self.imageScale += 0.5
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
      self.update()

  def zoomout(self):
    if self.imageScale > 0.5:
      self.imageScale -= 0.5
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
      self.update()

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
            else:
                raise NotImplementedError(f"Unsupported bayer pattern: {imgData.header['BAYERPAT']}")
            deb_finish_time = time.time_ns()
            deb_time = deb_finish_time - end_load_time

    self.image = img
    print(f"load_time: {load_time/1e9:0.3f}, deb_time: {deb_time/1e9:0.3f}")

    self.update()
    return self.image

  def resize(self, event):
    self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
    self.update()

  def highlightStars(self, star_centroids):
    if self.highlights is not None:
      self.imageCanvas.delete(self.highlights)
    else:
      self.highlights = "highlights"
    
    for sc_x, sc_y in star_centroids:
      sx = sc_x * self.scaleX
      sy = sc_y * self.scaleY
      item = self.imageCanvas.create_oval(sx-5, sy-5, sx+5, sy+5, outline="yellow")
      self.imageCanvas.itemconfig(item, tags=(self.highlights))

