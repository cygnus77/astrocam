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
from image_data import ImageData
import itertools
from sklearn.linear_model import LinearRegression


def cone_search_stardata(skymap: SkyMap, center: SkyCoord, fov_deg: float, mag_limit: float):
  stars = []
  for star in skymap.coneSearch(center, fov_deg):
    if 'mag' in star and star['mag'] < 11:
      s_coord = SkyCoord(star['ra'] * u.degree, star['dec'] * u.degree, frame=ICRS)
      x, y = project(s_coord.ra.degree, s_coord.dec.degree, center.ra.degree, center.dec.degree, 0)
      stars.append({
        "id": star["_id"], 
        "cluster_cx": x, "cluster_cy": y, 
        "ra": s_coord.ra.degree, "dec": s_coord.dec.degree,
        "mag": star["mag"]
      })
  df_ref = pd.DataFrame(stars)
  return df_ref


def platesolve(imageData: ImageData, center: SkyCoord, fov_deg: float=5.0, mag_limit: float=11.0):
  result = {
    'solved': False
  }

  with SkyMap() as sm:
    df_ref = cone_search_stardata(sm, center, fov_deg=fov_deg, mag_limit=mag_limit)

  df_tgt = imageData.stars
  # print(f"Num ref stars: {len(df_ref)}, Num tgt stars: {len(df_tgt)}")
  result['num_ref'] = len(df_ref)
  result['num_tgt'] = len(df_tgt)
  matcher = StarMatcher()
  tx, matcher_result = matcher.matchStarsToTx(df_ref, df_tgt, limit_ref_triangle_fov=1.0)

  # matcher_result = matcher.matchStars(df_ref, df_tgt, limit_ref_triangle_fov=1.0)
  result.update(matcher_result)

  # # print(f"Solver votes: {df_tgt.votes.sum()}; matches: {(~df_tgt.starno.isnull()).sum()} stars")
  # result['solver_votes'] = df_tgt.votes.sum()
  # result['matches'] = (~df_tgt.starno.isnull()).sum()

  # img_stars = df_tgt[~df_tgt.starno.isnull()][['starno','cluster_cx', 'cluster_cy', 'votes']]
  # img_ref_stars = df_ref[['id','cluster_cx', 'cluster_cy', 'ra', 'dec']].join(img_stars.set_index('starno'), rsuffix='r', how='right')

  # if len(img_ref_stars) < 3:
  #   return result

  # matched_star_triple = img_ref_stars.sort_values('votes', ascending=False)[:3]
  # src = np.array([(row.cluster_cx, row.cluster_cy) for _, row in matched_star_triple.iterrows()], dtype=np.float32)
  # dst = np.array([(row.cluster_cxr, row.cluster_cyr) for _, row in matched_star_triple.iterrows()], dtype=np.float32)

  # tx = cv2.getAffineTransform(src, dst)


  result['tx'] = tx
  df_ref[['img_cx', 'img_cy']] = df_ref.apply(lambda r: pd.Series(np.dot(tx, [r.cluster_cx, r.cluster_cy, 1])).astype(np.int32), axis=1)

  # Reassign stars
  def dist(x1,y1, x2,y2):
    return np.sqrt((y2-y1)**2+(x2-x1)**2)
  def reassign(t):
    x = df_ref.apply(lambda r: pd.Series([dist(t.cluster_cx, t.cluster_cy, r.img_cx, r.img_cy)]), axis=1)[0]
    m = x.min()
    if m < 25:
      idx = x.argmin()
      return pd.Series([idx, df_ref.iloc[idx].ra, df_ref.iloc[idx].dec])
    else:
      return pd.Series([None, None, None])
  df_tgt[['starno', 'ra', 'dec']] = df_tgt.apply(reassign, axis=1)

  nonantgt = df_tgt[ (~df_tgt.ra.isna()) & (~df_tgt.dec.isna())]
  X = nonantgt[['cluster_cx', 'cluster_cy']]
  y = nonantgt[['ra', 'dec']]
  reg = LinearRegression().fit(X, y)
  pred_center = reg.predict(pd.DataFrame([{"cluster_cx": imageData.rgb24.shape[1]//2, "cluster_cy": imageData.rgb24.shape[0]//2}]))[0]
  pred_center = SkyCoord(pred_center[0] * u.degree, pred_center[1] * u.degree, frame=ICRS)
  separation_arcmin = center.separation(pred_center).arcminute
  result['center'] = pred_center
  result['separation_arcmin'] = separation_arcmin
  # print(f"Image Center RA,DEC: {pred_center}")
  # print(f"Separation from target: {center.separation(pred_center).arcminute}")

  if center.separation(pred_center).arcminute > 20:
    return result
  
  result['solved'] = True

  df_tgt['name'] = None
  for idx, star in df_tgt[~df_tgt.starno.isnull()].iterrows():
    df_tgt.loc[idx, 'name'] = df_ref.loc[star.starno].id

  return result