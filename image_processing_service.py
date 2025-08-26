from service_base import ServiceBase
import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk


class ImageProcessingService(ServiceBase):

    def __init__(self, tk_root):
        super().__init__(tk_root)

    def process(self):
        
        if self.job['cmd'] == 'compute_stars':
            imageData = self.job['imageData']
            imageData.computeStars()
            self.output = imageData
        elif self.job['cmd'] == 'resize':
            imageData = self.job['imageData']
            w, h = self.job['w'], self.job['h']
            scaledImg = cv2.resize(imageData.rgb24, dsize=(int(w*self.job['imageScale']), int(h*self.job['imageScale'])), interpolation=cv2.INTER_LINEAR)
            if scaledImg.dtype == np.uint16:
                scaledImg = (scaledImg / 256).astype(np.uint8)

            img = scaledImg
            if len(self.job['gamma_table'].shape) == 2:
                r = cv2.LUT(img[:, :, 0], self.job['gamma_table'][:, 0])
                g = cv2.LUT(img[:, :, 1], self.job['gamma_table'][:, 1])
                b = cv2.LUT(img[:, :, 2], self.job['gamma_table'][:, 2])
                img = np.stack([r, g, b], axis=-1)
            else:
                img = cv2.LUT(img, self.job['gamma_table'])

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.output = (scaledImg, ImageTk.PhotoImage(image=Image.fromarray(img)))

        elif self.job['cmd'] == 'stretch_to_photoimage':
            img = self.job['image']

            if len(self.job['gamma_table'].shape) == 2:
                r = cv2.LUT(img[:, :, 0], self.job['gamma_table'][:, 0])
                g = cv2.LUT(img[:, :, 1], self.job['gamma_table'][:, 1])
                b = cv2.LUT(img[:, :, 2], self.job['gamma_table'][:, 2])
                img = np.stack([r, g, b], axis=-1)
            else:
                img = cv2.LUT(img, self.job['gamma_table'])

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.output = ImageTk.PhotoImage(image=Image.fromarray(img))
        else:
            raise RuntimeError(f"Unknown command: {self.job['cmd']}")

    def computeStars(self, imageData, on_success):
        return self.start_job({'cmd': 'compute_stars', 'imageData': imageData}, on_success=on_success)

    def resize(self, imageData, w, h, imageScale, gamma_table, on_success):
        return self.start_job({'cmd': 'resize', 'imageData': imageData, 'w': w, 'h': h, 'imageScale': imageScale, 'gamma_table': gamma_table}, on_success=on_success)

    def stretch_to_photoimage(self, image, gamma_table, on_success):
        return self.start_job({'cmd': 'stretch_to_photoimage', 'image': image, 'gamma_table': gamma_table}, on_success=on_success)
