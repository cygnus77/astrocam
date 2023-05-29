from datetime import datetime
import tkinter as tk
import tkinter.ttk as ttk
import numpy as np
from fwhm.star_finder import StarFinder
from fwhm.star_matcher import StarMatcher
from ui.base_widget import BaseWidget
import pandas as pd
import cv2

class FWHMWidget(BaseWidget):

  def __init__(self, parentFrame, imageViewer):
    super().__init__()
    self.imageViewer = imageViewer
    self.starFinder = StarFinder()
    self.starMatcher = StarMatcher()

    self.stats = tk.StringVar()
    ttk.Label(parentFrame, textvariable=self.stats).pack(fill=tk.X, side=tk.TOP)

    self.frame_idx = 0
    self.df_ref = None
    self.df_fwhm = None

  def update(self, img16: np.ndarray):
    try:
      assert(img16.dtype == np.uint16)
      assert(len(img16.shape) == 3)
      assert(img16.shape[2] == 3)
      img16 = cv2.cvtColor(img16, cv2.COLOR_RGB2GRAY)
      img8 = ((img16 / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)
      numStars = 40 if self.df_ref is None else 10
      star_img, df_tgt = self.starFinder.find_stars(img8=np.squeeze(img8), img16=np.squeeze(img16), topk=numStars)
      if self.df_ref is None:
        self.df_ref = df_tgt

      df_matched = self.starMatcher.matchStars(self.df_ref, df_tgt)
      print(f"Num matched: {len(df_matched)}")
      if self.df_fwhm is None:
        self.df_fwhm = df_matched[['index_ref', 'fwhm_x_ref', 'fwhm_y_ref', 'fwhm_x_tgt', 'fwhm_y_tgt']]
      else:
        self.df_fwhm = pd.merge(left=self.df_fwhm, right=df_matched[['index_ref', 'fwhm_x_tgt', 'fwhm_y_tgt']], how='left', on='index_ref', suffixes=('', f'_{self.frame_idx:05d}'))

      self.stats.set(f"Ave FWHM: {df_tgt.fwhm_x.mean():.3f}, {df_tgt.fwhm_y.mean():.3f}")
      self.imageViewer.highlightStars([
        (int(x),int(y)) for x,y in zip(df_tgt.cluster_cx,	df_tgt.cluster_cy)
      ])

      timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
      with open("fwhm_data/fwhm_trends.csv", "at") as f:
        f.write(f"{timestamp},{df_tgt.fwhm_x.mean():.3f},{df_tgt.fwhm_y.mean():.3f}\n")

      self.df_fwhm.to_csv(f"fwhm_data/fwhm_{timestamp}.csv")

      self.frame_idx += 1
    except Exception as e:
      print(e)
