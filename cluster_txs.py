# %%
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
import matplotlib.pyplot as plt
from pathlib import Path


# %% [markdown]
# |    | Initial     |    Corrected |
# | --- | ---- | --- |
# | Albereo |
# | RA  | 19h31m39.9612s  | 19h30m52.1928s |
# | Dec | 28d00m47.8116s  | 28d02m10.5612 |
# | RA  | 19h30m43.2072s  | 19h30m40.8528s |
# | Dec | 27d57m35.4204s  | 28d00m37.9908s |
# | NGC 7000 |
# | RA  | 20h58m46.9452s  | 20h58m50.6532s |
# | Dec  | 44d19m48.0612s  | 44d12m19.0872s |
# | Crescent Nebula |
# | RA  | 20h12m57.7404s  | 20h13m01.7652s |
# | Dec | 38d25m36.714s  |  38d30m20.232s |
# | Deneb |
# | RA  | 20h41m27.2616s  | |
# | Dec | 45d16m38.3736s  | |

# %%
center = SkyCoord.from_name("NGC6888")
fname = r'D:/Astro/plate-solving-samples/NGC6888/Light_03275_10.0sec_300gain_-0.3C.fit'
print(center, fname)

# %%
# # M101 - EDT115:
# center, fname = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS), r"D:\Astro\20230319-M81M82_M101_M13\Light-M101-300sec\Light_ASIImg_300sec_Bin1_-9.4C_gain200_2023-03-20_023749_frame0026.fit"

# # M101 - C11:
# # center, fname = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS), r"D:\Astro\20230528-M101-Supernova\20230601\M101\Light\Light_02780_180.0sec_300gain_0.0C.fit"
# # center, fname = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS), r"D:\Astro\20230528-M101-Supernova\M101\Light\Light_02650_180.0sec_300gain_-0.3C.fit"
# # center, fname = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS), r"D:\Astro\20230528-M101-Supernova\M101\Light\Light_02693_180.0sec_300gain_0.0C.fit"

# # Bubble Nebula - EDT115:
# #center, fname = SkyCoord("23h20m48.3s" "+61d12m06s", frame=ICRS), r"D:\Astro\20230818-uacnj\Bubble\Light\Light_03128_180.0sec_200gain_0.0C.fit"




# %% [markdown]
# ## Cone search given object sky-coord

# %%
import itertools

def cone_search_stardata(skymap: SkyMap, center: SkyCoord, fov_deg: float):
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

with SkyMap() as sm:
  df_ref = cone_search_stardata(sm, center, fov_deg=5.0)



# %% [markdown]
# ## Read image and run star matching

with fits.open(fname) as f:
    ph = f[0]
    img = ph.data
    img = np.expand_dims(img, axis=2)
    # img16 = debayer_superpixel(img)
    img16 = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2BGR) # RGGB pattern

assert(img16.dtype == np.uint16)
assert(len(img16.shape) == 3)
assert(img16.shape[2] == 3)
img16 = cv2.cvtColor(img16, cv2.COLOR_BGR2GRAY)
img8 = ((img16 / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)
numStars = 20
# img8 = cv2.equalizeHist(img8)
star_img, df_tgt = StarFinder().find_stars(img8=np.squeeze(img8), img16=np.squeeze(img16), topk=numStars)

# votes, vVotingPairs = StarMatcher().matchStars(df_ref, df_tgt, return_merged=False)



# %%
from scipy.spatial import Delaunay
import numpy as np
points = np.array(df_tgt.apply(lambda x: [x.cluster_cx, x.cluster_cy], axis=1).to_list())
tri = Delaunay(points)


# %%
m = StarMatcher()

tri_tgt = pd.DataFrame(m._getVertexSortedTriangles(df_tgt, itertools.combinations(df_tgt.index, 3), fov_deg=None))

# tri_ref =  m._getVertexSortedDelaunayTriangles(df_ref, fov_deg=1.0)


# tri_ref = []
# for mag_lim in range(int(df_ref.mag.min())+1, int(df_ref.mag.max())+2, 1):
#   df = df_ref[df_ref.mag <= mag_lim]
#   print(mag_lim, len(df))
#   if len(df) < 3: continue
#   tri_ref.append(m._getVertexSortedDelaunayTriangles(df, fov_deg=1.0))
# tri_ref = pd.concat(tri_ref)


D = None
added_triangles = set()
vTriangles = []
initial_points = []
pt_idx = []
for mag in range(int(df_ref.mag.min()), int(df_ref.mag.max())+1, 1):
  df = df_ref[(df_ref.mag >= mag) & (df_ref.mag < mag+1)]

  points = []
  for idx, r in df.iterrows():
    points.append([r.cluster_cx, r.cluster_cy])
    pt_idx.append(idx)

  if D is None:
    if len(initial_points) < 4:
      initial_points.extend(points)
    
    if len(initial_points) >= 4:
      D = Delaunay(initial_points, incremental=True)
  else:
    D.add_points(points)

    print(mag, len(df))
    if len(df) < 3: continue

    pt_indices = []
    for x, y, z in D.simplices:
      a, b, c = pt_idx[x], pt_idx[y], pt_idx[z]
      if (a,b,c) not in added_triangles:
        added_triangles.add((a, b, c))
        pt_indices.append([a, b, c])

    vTriangles.extend(m._getVertexSortedTriangles(df_ref, pt_indices, fov_deg=1.0))

vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
tri_ref = pd.DataFrame(vTriangles)

print(f"Ref triangles: {len(tri_ref)}, Tgt triangles: {len(tri_tgt)}")



# %%
TRIANGLETOLERANCE = 1e-2

txs = []
minIdx = -1

for tgt in tri_tgt.itertuples():
    similar_triangles = tri_ref[
        (tri_ref.fX >= tgt.fX - TRIANGLETOLERANCE/2) &
        (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE/2) &
        (tri_ref.fY >= tgt.fY - TRIANGLETOLERANCE/2) &
        (tri_ref.fY <= tgt.fY + TRIANGLETOLERANCE/2)
    ]
    for r in similar_triangles.itertuples():
        ra = df_ref.iloc[r.A][['cluster_cx', 'cluster_cy']].tolist()
        rb = df_ref.iloc[r.B][['cluster_cx', 'cluster_cy']].tolist()
        rc = df_ref.iloc[r.C][['cluster_cx', 'cluster_cy']].tolist()
        ta = df_tgt.iloc[tgt.A][['cluster_cx', 'cluster_cy']].tolist()
        tb = df_tgt.iloc[tgt.B][['cluster_cx', 'cluster_cy']].tolist()
        tc = df_tgt.iloc[tgt.C][['cluster_cx', 'cluster_cy']].tolist()
        src = np.stack([ra, rb, rc], dtype=np.float32)
        dst = np.stack([ta, tb, tc], dtype=np.float32)
        tx = cv2.getAffineTransform(src, dst)
        txs.append([tx, 1])
        
        mapped = False
        for i, (e,c) in enumerate(txs):
            if np.linalg.norm(tx - e) < 1000:
                txs[i][1] += 1
                mapped = True
                # print(tx,r.A, r.B, r.C, tgt.A, tgt.B, tgt.C)
                break
        if not mapped:
            txs.append([tx, 1])
print("Max:", max(map(lambda x: x[1], txs)))

# %%
txs = sorted(txs, key=lambda x: x[1])
tx_arr = np.array(list(map(lambda x: x[0], txs))).reshape(-1,6)
tx_counts = np.array(list(map(lambda x: x[1], txs))).reshape(-1)


# %%
from sklearn.decomposition import PCA
pca = PCA(n_components=2)
pca.fit(tx_arr)
reduced_txs = pca.transform(tx_arr)

plt.scatter(reduced_txs[:,0], reduced_txs[:,1], c=tx_counts)
plt.show()

# TODO: Histogram of count of merged txs

# %%
tx, num_matches = txs[-1]

# %% [markdown]
# ## Apply transform with dot-product

# %%
df_ref[['img_cx', 'img_cy']] = df_ref.apply(lambda r: pd.Series(np.dot(tx, [r.cluster_cx, r.cluster_cy, 1])).astype(np.int32), axis=1)



# %%
# pts = tx * pts
plt.imshow(img8, cmap='gray')
# plt.scatter(tx_pts[0, :, 0], tx_pts[0, :, 1], alpha=0.2)
plt.scatter(df_ref.img_cx, df_ref.img_cy, alpha=0.2)
plt.show()


# %%

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


# %%
plt.imshow(img8, cmap='gray')
for idx, star in df_tgt[~df_tgt.starno.isnull()].iterrows():
    # print(star.starno, (star.cluster_cx, star.cluster_cy))
    plt.annotate(df_ref.loc[star.starno].id, (star.cluster_cx, star.cluster_cy), fontsize=6, color='yellow')

plt.show()


# %%
from sklearn.linear_model import LinearRegression

nonantgt = df_tgt[ (~df_tgt.ra.isna()) & (~df_tgt.dec.isna())]
X = nonantgt[['cluster_cx', 'cluster_cy']]
y = nonantgt[['ra', 'dec']]
reg = LinearRegression().fit(X, y)
pred_center = reg.predict([[img8.shape[1]//2, img8.shape[0]//2]])[0]
pred_center = SkyCoord(pred_center[0] * u.degree, pred_center[1] * u.degree, frame=ICRS)
print(f"Image Center RA,DEC: {pred_center}")
print(f"Separation from target: {center.separation(pred_center).arcminute}")

