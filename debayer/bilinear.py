import numpy as np
import cv2

g_kernel = np.array([
  [0, 1, 0],
  [1, 4, 1],
  [0, 1, 0],
]) / 4
rb_kernel = np.array([
  [1, 2, 1],
  [2, 4, 2],
  [1, 2, 1],
]) / 4

def norm(img):
  img = img - np.min(img)
  img = img / np.max(img)
  return img

def debayer_bilinear(img: np.ndarray):
  r_m = np.zeros(img.shape, dtype=np.uint16)
  g_m = np.zeros(img.shape, dtype=np.uint16)
  b_m = np.zeros(img.shape, dtype=np.uint16)

  r_m[0::2, 0::2] = 1
  g_m[1::2, 0::2] = 1
  g_m[0::2, 1::2] = 1
  b_m[1::2, 1::2] = 1

  R = cv2.filter2D(img.astype(np.float32) * r_m, ddepth=cv2.CV_32F, kernel=rb_kernel, anchor=(-1, -1))
  G = cv2.filter2D(img.astype(np.float32) * g_m, ddepth=cv2.CV_32F, kernel=g_kernel, anchor=(-1, -1))
  B = cv2.filter2D(img.astype(np.float32) * b_m, ddepth=cv2.CV_32F, kernel=rb_kernel, anchor=(-1, -1))

  deb_img = np.stack([norm(R), norm(G), norm(B)], axis=2)
  deb_img = np.nan_to_num(deb_img, nan=0)
  return deb_img
