import rawpy
import numpy as np
import cv2
from tqdm import tqdm
import pandas as pd
import math
from fwhm.fwhm import getFWHM_GaussianFitScaledAmp
from fwhm.star_centroid import iwc_centroid
from astropy.io import fits

class StarFinder():
  def __init__(self):
    self.Bs = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(7,7))
    Bmi = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(21,21))
    self.Be = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(25,25))
    Bmo = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    d = (Bmo.shape[0] - Bmi.shape[0]) // 2
    self.Bm = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    self.Bm[d:d+Bmi.shape[0], d:d+Bmi.shape[0]] -= Bmi

  def find_stars(self, gray: np.ndarray, topk:int=None):
    img_height = gray.shape[0]
    img_width = gray.shape[1]
    K = cv2.morphologyEx(gray, cv2.MORPH_OPEN, self.Bs)
    N = cv2.morphologyEx(cv2.morphologyEx(gray, cv2.MORPH_DILATE, self.Bm), cv2.MORPH_ERODE, self.Be)
    R = K - np.minimum(K,N)
    numstars, labels, stats, centroids = cv2.connectedComponentsWithStats(R, 4, cv2.CV_16U, cv2.CCL_WU)

    # Fixed star area
    # width = 19
    # height = 19
    # Use maximum area for all stars
    # for staridx in range(1, numstars):
    #   width = max(width, stats[staridx, cv2.CC_STAT_WIDTH])
    #   height = max(height, stats[staridx, cv2.CC_STAT_HEIGHT])
    # print(f"Star dim: {width}, {height}")

    bboxes = []
    for staridx in tqdm(range(1, numstars), desc="Calculating FWHM"):
      centroid_x, centroid_y = centroids[staridx]
      # Per-star area
      width = stats[staridx, cv2.CC_STAT_WIDTH]
      height = stats[staridx, cv2.CC_STAT_HEIGHT]
      min_row = int(max(0, centroid_y - (height/2)))
      max_row = int(min(img_height, centroid_y + (height/2)+1))
      min_col = int(max(0, centroid_x - (width/2)))
      max_col = int(min(img_width, centroid_x + (width/2)+1))
      star = gray[min_row:max_row, min_col:max_col]
      # Recalculate centroid
      iwc_cx, iwc_cy = iwc_centroid(star)

      def tile(tile_size):
        tiles_per_row = int((img_width + tile_size - 1) / tile_size)
        tile_x = round(centroid_x / tile_size)
        tile_y = round(centroid_y / tile_size)
        tile_no = tile_x + tile_y * tiles_per_row
        return tile_no

      fwhm_x, fwhm_y, curve_cx, curve_cy = getFWHM_GaussianFitScaledAmp(star)
      bboxes.append({'area':stats[staridx, cv2.CC_STAT_AREA],
                     'cluster_cx': centroid_x,
                     'cluster_cy': centroid_y,
                     'iwc_cx': iwc_cx,
                     'iwc_cy': iwc_cy,
                     'gaussian_cx': curve_cx,
                     'gaussian_cy': curve_cy,
                     'box':[min_col, min_row, max_col, max_row],
                     'tile_4': tile(4),
                     'tile_32': tile(32),
                     'fwhm_x': fwhm_x,
                     'fwhm_y': fwhm_y,
                    })

    sorted_bboxes = sorted(bboxes, key=lambda x: x['area'], reverse=True)
    if topk is not None:
      sorted_bboxes = sorted_bboxes[:topk]
    df = pd.DataFrame(sorted_bboxes)
    return R, df

  def getStarData(self, fname, topk=20):
    if str(fname)[-3:].lower() == 'nef':
      with open(fname, "rb") as f:
        rawimg = rawpy.imread(f)
        img = rawimg.postprocess()
    else:
      f = fits.open(fname)
      ph = f[0]
      img = ph.data

      if ph.header['BAYERPAT'] == 'RGGB':
          deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2RGB)
          img = deb.astype(np.float32) / np.iinfo(deb.dtype).max
          img = (img * 255).astype(np.uint8)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    star_img, bboxes = self.find_stars(gray, topk=topk)
    return {  "image": star_img,
              "stars": bboxes,}

if __name__ == "__main__":
  star_file = r"C:\code\astrocam\outoffocus\Image741.nef"
  s = StarFinder()
  stars = s.getStarData(star_file)
  print(stars)

