import numpy as np
import cv2
from debayer.superpixel import debayer_superpixel
from astropy.io import fits
from fwhm.star_matcher import StarMatcher
from fwhm.star_finder import StarFinder
import pandas as pd
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.coordinates import ICRS
from skymap.skymap import SkyMap
from skymap.stardb.render_view import project
from snap_process import ImageData
import itertools
from sklearn.linear_model import LinearRegression

def cone_search_stardata(skymap: SkyMap, center: SkyCoord, fov_deg: float):
  stars = []
  for star in itertools.islice(skymap.coneSearch(center, fov_deg), 100):
    if 'mag' in star and star['mag']: #and star['mag'] < 11:
      print(star)
      s_coord = SkyCoord(star['icrs']['deg']['ra'] * u.degree, star['icrs']['deg']['dec'] * u.degree, frame=ICRS)
      x, y = project(s_coord.ra.degree, s_coord.dec.degree, center.ra.degree, center.dec.degree, 0)
      stars.append({"id": star["_id"], "cluster_cx": x, "cluster_cy": y, "ra": s_coord.ra.degree, "dec": s_coord.dec.degree})
  df_ref = pd.DataFrame(stars)
  return df_ref


def platesolve(imageData: ImageData, df_tgt: pd.DataFrame, center: SkyCoord, fov_deg: float=3.0):
  with SkyMap() as sm:
    df_ref = cone_search_stardata(sm, center, fov_deg=fov_deg)

  img16 = debayer_superpixel(imageData.image)

  assert(img16.dtype == np.uint16)
  assert(len(img16.shape) == 3)
  assert(img16.shape[2] == 3)
  img16 = cv2.cvtColor(img16, cv2.COLOR_RGB2GRAY)
  img8 = ((img16 / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)
  numStars = 20
  #img8 = cv2.equalizeHist(img8)
  star_img, df_tgt = StarFinder().find_stars(img8=np.squeeze(img8), img16=np.squeeze(img16), topk=numStars)

  matcher = StarMatcher()
  matcher.matchStars(df_ref, df_tgt, limit_ref_triangle_fov=1.0)

  if df_tgt.votes.sum() < 100 or df_tgt.starno.isnull().sum() < 3:
    return None

  img_stars = df_tgt[~df_tgt.starno.isnull()][['starno','cluster_cx', 'cluster_cy', 'votes']]
  img_ref_stars = df_ref[['id','cluster_cx', 'cluster_cy', 'ra', 'dec']].join(img_stars.set_index('starno'), rsuffix='r', how='right')

  matched_star_triple = img_ref_stars.sort_values('votes', ascending=False)[:3]
  src = np.array([(row.cluster_cx, row.cluster_cy) for _, row in matched_star_triple.iterrows()], dtype=np.float32)
  dst = np.array([(row.cluster_cxr, row.cluster_cyr) for _, row in matched_star_triple.iterrows()], dtype=np.float32)
  import cv2
  tx = cv2.getAffineTransform(src, dst)
  df_ref[['img_cx', 'img_cy']] = df_ref.apply(lambda r: pd.Series(np.dot(tx, [r.cluster_cx, r.cluster_cy, 1])).astype(np.int32), axis=1)

  # Reassign stars
  def dist(x1,y1, x2,y2):
    return np.sqrt((y2-y1)**2+(x2-x1)**2)
  def reassign(t):
    x = df_ref.apply(lambda r: pd.Series([dist(t.cluster_cx, t.cluster_cy, r.img_cx, r.img_cy)]), axis=1)[0]
    m = x.min()
    if m < 25:
      return x.argmin()
    else:
      return None
  df_tgt['starno'] = df_tgt.apply(reassign, axis=1)


  X = df_ref[['img_cx', 'img_cy']]
  y = df_ref[['ra', 'dec']]
  reg = LinearRegression().fit(X, y)
  pred_center = reg.predict([[img8.shape[1]//2, img8.shape[0]//2]])[0]
  pred_center = SkyCoord(pred_center[0] * u.degree, pred_center[1] * u.degree, frame=ICRS)
  print(f"Image Center RA,DEC: {pred_center}")
  print(f"Separation from target: {center.separation(pred_center).arcminute}")

  df_tgt['name'] = None
  for idx, star in df_tgt[~df_tgt.starno.isnull()].iterrows():
    df_tgt.loc[idx, 'name'] = df_ref.loc[star.starno].id

  return pred_center
