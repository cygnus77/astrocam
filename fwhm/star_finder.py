from pathlib import Path
import rawpy
import numpy as np
import cv2
from tqdm import tqdm
import pandas as pd
import math
from fwhm.fwhm import getFWHM_GaussianFitScaledAmp, fwhm1d, fwhm2d, fitgaussian2d
from fwhm.star_centroid import iwc_centroid
from astropy.io import fits
from xisf.xisf_parser import read_xisf

# from debayer.nn_debayer import make_debayer
# debayer = make_debayer()

class StarFinder():
  def __init__(self):
    self.Bs = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(7,7))
    Bmi = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(21,21))
    self.Be = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(25,25))
    Bmo = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    d = (Bmo.shape[0] - Bmi.shape[0]) // 2
    self.Bm = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(29,29))
    self.Bm[d:d+Bmi.shape[0], d:d+Bmi.shape[0]] -= Bmi

  def find_stars(self, img8: np.ndarray, img16: np.ndarray, topk:int=None):
    img_height = img8.shape[0]
    img_width = img8.shape[1]
    K = cv2.morphologyEx(img8, cv2.MORPH_OPEN, self.Bs)
    N = cv2.morphologyEx(cv2.morphologyEx(img8, cv2.MORPH_DILATE, self.Bm), cv2.MORPH_ERODE, self.Be)
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
      min_row = int(max(0, centroid_y - height))
      max_row = int(min(img_height, centroid_y + height+1))
      min_col = int(max(0, centroid_x - width))
      max_col = int(min(img_width, centroid_x + width+1))
      star = img16[min_row:max_row, min_col:max_col]
      # Recalculate centroid
      iwc_cx, iwc_cy = iwc_centroid(star)

      def tile(tile_size):
        tiles_per_row = int((img_width + tile_size - 1) / tile_size)
        tile_x = round(centroid_x / tile_size)
        tile_y = round(centroid_y / tile_size)
        tile_no = tile_x + tile_y * tiles_per_row
        return tile_no

      # fwhm_x, fwhm_y, curve_cx, curve_cy = getFWHM_GaussianFitScaledAmp(star)
      # fwhm_x = fwhm1d(star[int(max_row-min_row)//2, :])
      # fwhm_y = fwhm1d(star[:, int(max_col-min_col)//2])
      curve_cx, curve_cy, fwhm_y, fwhm_x = fitgaussian2d(star, circular=False, centered=False)
      # fwhm_x, fwhm_y = star.shape
      #fwhm_x, fwhm_y, curve_cx, curve_cy = getFWHM(star)
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
    ext = Path(fname).suffix.lower()

    if ext == '.nef':
      with open(fname, "rb") as f:
        rawimg = rawpy.imread(f)
        img = rawimg.postprocess()
        img8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img16 = (np.iinfo(np.uint16).max * (img8.astype(np.float32) / 255.0)).astype(np.uint16)
      hdr = None

    elif ext == '.fit':
      f = fits.open(fname)
      ph = f[0]
      img = ph.data
      hdr = ph.header
      if hdr is not None and hdr['BAYERPAT'] == 'RGGB' and img.dtype == np.uint16:
        deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2RGB)
        # deb = debayer_superpixel(np.expand_dims(img, axis=2))
        # deb = debayer(img.astype(np.float32) / np.iinfo(np.uint16).max)
        deb = cv2.cvtColor(deb, cv2.COLOR_RGB2GRAY)
        img16 = deb
        img8 = ((deb / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)

    elif ext == '.xisf':
      img, hdr = read_xisf(fname)
      img16 = (np.iinfo(np.uint16).max * img).astype(np.uint16)
      img8 = (np.iinfo(np.uint8).max * img).astype(np.uint8)

    star_mask, bboxes = self.find_stars(img8=np.squeeze(img8), img16=np.squeeze(img16), topk=topk)
    return {  "star_mask": star_mask,
              "image": img16,
              "stars": bboxes,}

if __name__ == "__main__":
  star_file = r"D:\Astro\Objects\C30\subs\Light_00934_180.0sec_200gain_-0.3C_c_a.xisf"
  s = StarFinder()
  stars = s.getStarData(star_file)
  print(stars)

