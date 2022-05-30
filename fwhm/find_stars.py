from json import load
import rawpy
import numpy as np
import cv2
from sympy import root

class StarFinder():
  def __init__(self) -> None:
    self.Bs = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(7,7))
    Bmi = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(21,21))
    self.Be = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(25,25))
    Bmo = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    d = (Bmo.shape[0] - Bmi.shape[0]) // 2
    self.Bm = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    self.Bm[d:d+Bmi.shape[0], d:d+Bmi.shape[0]] -= Bmi
   
  def find_stars(self, gray: np.ndarray):
    img_height = gray.shape[0]
    img_width = gray.shape[1]
    K = cv2.morphologyEx(gray, cv2.MORPH_OPEN, self.Bs)
    N = cv2.morphologyEx(cv2.morphologyEx(gray, cv2.MORPH_DILATE, self.Bm), cv2.MORPH_ERODE, self.Be)
    R = K - np.minimum(K,N)
    numstars, labels, stats, centroids = cv2.connectedComponentsWithStats(R, 4, cv2.CV_16U, cv2.CCL_WU)

    bboxes = []
    for staridx in range(numstars):
      centroid_x, centroid_y = centroids[staridx]
      width = stats[staridx, cv2.CC_STAT_WIDTH]
      height = stats[staridx, cv2.CC_STAT_HEIGHT]
      min_row = int(max(0, centroid_y - height / 2))
      max_row = int(min(img_height, centroid_y + (height / 2) + 1))
      min_col = int(max(0, centroid_x - width / 2))
      max_col = int(min(img_width, centroid_x + (width / 2) + 1))

      def tile(tile_size):
        tiles_per_row = int((img_width + tile_size - 1) / tile_size)
        tile_x = round(centroid_x / tile_size)
        tile_y = round(centroid_y / tile_size)
        tile_no = tile_x + tile_y * tiles_per_row
        return tile_no

      #star = gray[min_row:max_row, min_col:max_col]
      #stars.append(star)
      bboxes.append({'area':stats[staridx, cv2.CC_STAT_AREA],
                     'centroid':[centroid_x, centroid_y],
                     'box':[min_col, min_row, max_col, max_row],
                     'tile_4': tile(4),
                     'tile_16': tile(16),
                     'tile_32': tile(32),
                    })

    return R, bboxes

  def getStarData(self, fname):
    with open(fname, "rb") as f:
      rawimg = rawpy.imread(f)
      img = rawimg.postprocess()
      img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
      star_img, bboxes = self.find_stars(img)
      return {  "image": star_img, 
                "stars": bboxes,}

if __name__ == "__main__":
  out_of_focus = r"D:\Astro\20220430-whale\outoffocus\Image741.nef"
  in_focus = r"D:\Astro\20220430-whale\light\Image752.nef"

  s = StarFinder()
  stars = s.getStarData(in_focus)
  print(stars)

