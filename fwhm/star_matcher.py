import importlib
import rawpy
import numpy as np
import cv2
import pandas as pd
import matplotlib.pyplot as plt
from itertools import combinations, product
from collections import defaultdict
import math
from scipy.spatial import Delaunay
from .star_finder import StarFinder
class StarMatcher:

    def matchStars(self, df_ref: pd.DataFrame, df_tgt: pd.DataFrame, 
                   vertex_sorted = True,
                   down_votes = True,
                   absolute_similar = True,
                   vote_with_conf = True,
                   limit_ref_triangle_fov=None):
        """ matchStars in a reference and target dataframes from either database or a photo
            Adds columns to target dataframe: starno (index in reference dataframe) and votes (int)
            Returns votes and voting pairs for informational purposes
            Code developed in refine_location.ipynb
            NOTE: must reset_index on target if it will be reused in future match calls
        """
        result = {
            'vertex_sorted': vertex_sorted,
            'down_votes': down_votes,
            'absolute_similar': absolute_similar,
            'vote_with_conf': vote_with_conf,
            'limit_ref_triangle_fov': limit_ref_triangle_fov
        }

        if vertex_sorted:
            # tri_ref = self._getVertexSortedTriangles(df_ref, combinations(df_ref.index, 3), fov_deg=limit_ref_triangle_fov)
            tri_ref = pd.DataFrame(self._getVertexSortedDelaunayTriangles(df_ref, fov_deg=limit_ref_triangle_fov))
            tri_tgt = pd.DataFrame(self._getVertexSortedTriangles(df_tgt, combinations(df_tgt.index, 3), fov_deg=None))
        else:
            tri_ref = self._getTriangles(df_ref)
            tri_tgt = self._getTriangles(df_tgt)

        if len(tri_ref) == 0 or len(tri_tgt) == 0:
            return None

        # print(f"Ref triangles: {len(tri_ref)}, Tgt triangles: {len(tri_tgt)}")
        result['ref_triangles'] = len(tri_ref)
        result['tgt_triangles'] = len(tri_tgt)

        tri_comp = len(tri_ref) * len(tri_tgt)
        TRIANGLETOLERANCE = 5000 / tri_comp
        # if tri_comp > 3e6:
        #     TRIANGLETOLERANCE = 1e-4
        # elif tri_comp > 1e6:
        #     TRIANGLETOLERANCE = 1e-3
        # elif tri_comp > 1e-5:
        #     TRIANGLETOLERANCE = 5e-3
        # else:
        #     TRIANGLETOLERANCE = 1e-2

        votes = np.zeros((len(df_ref)+1, len(df_tgt)+1), dtype=np.float32)

        for tgt in tri_tgt.itertuples():
            if absolute_similar:
                similar_triangles = tri_ref[
                    (tri_ref.fX >= tgt.fX - TRIANGLETOLERANCE/2) &
                    (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE/2) &
                    (tri_ref.fY >= tgt.fY - TRIANGLETOLERANCE/2) &
                    (tri_ref.fY <= tgt.fY + TRIANGLETOLERANCE/2)
                ]
            else:
                ref_matches = tri_ref[
                    (tri_ref.fX >= tgt.fX - TRIANGLETOLERANCE/2) &
                    (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE/2)]
                similar_triangles = ref_matches[(ref_matches.fX-tgt.fX)**2 + (ref_matches.fY-tgt.fY)**2 < TRIANGLETOLERANCE**2]

            for ref in similar_triangles.itertuples():
                if vote_with_conf:
                    err = ((ref.fX-tgt.fX)**2 + (ref.fY-tgt.fY)**2)
                    upvote = 1/(np.exp(err*100))
                    downvote = upvote / 2
                else:
                    upvote = 1
                    downvote = 1/2

                if vertex_sorted:
                    # expect matched ABC vertices
                    votes[ref.A, tgt.A] += upvote
                    votes[ref.B, tgt.B] += upvote
                    votes[ref.C, tgt.C] += upvote

                    if down_votes:
                        votes[ref.A, tgt.B] -= downvote
                        votes[ref.A, tgt.C] -= downvote

                        votes[ref.B, tgt.A] -= downvote
                        votes[ref.B, tgt.C] -= downvote
                        
                        votes[ref.C, tgt.A] -= downvote
                        votes[ref.C, tgt.B] -= downvote
                else:
                    # expect unordered star indices s1, s2, s3
                    for a,b in product([ref.s1, ref.s2, ref.s3], [tgt.s1, tgt.s2, tgt.s3]):
                        votes[int(a), b] += upvote
            
        # print(f"TRIANGLETOLERANCE: {TRIANGLETOLERANCE}")
        # print(f"Total triangle comparisons: {len(tri_ref) * len(tri_tgt)}")
        # print(f"Total votes: {np.sum(votes)}, hit-ratio: {np.sum(votes) / (len(tri_ref) * len(tri_tgt))}")
        result["triangle_tolerance"] = TRIANGLETOLERANCE
        result["triangle_comparisons"] = len(tri_ref) * len(tri_tgt)
        result["total_votes"] = np.sum(votes)
        result["hit_ratio"] = np.sum(votes) / (len(tri_ref) * len(tri_tgt))

        # Produce sorted list of star pairs with highest votes
        vVotingPairs = np.column_stack(np.unravel_index(np.argsort(votes, axis=None), shape=votes.shape))[::-1]

        cutoff = votes.max() / 4
        # print(f"Vote cutoff threshold: {cutoff}")
        topVotePairs = list(filter(lambda r: votes[r[0],r[1]] > cutoff, vVotingPairs))

        matches = []
        for vp in topVotePairs:
            s1, s2 = vp
            # if s1 == 0 or s2 == 0: # WHY ?
            #     continue
            if np.argmax(votes[:, s2]) == s1 and np.argmax(votes[s1, :]) == s2:
                matches.append((s1, s2))

        df_tgt['starno'] = None
        df_tgt['votes'] = None
        for m1, m2 in matches:
            df_tgt.loc[m2, 'starno'] = m1
            df_tgt.loc[m2, 'votes'] = votes[m1, m2]

        result['votes'] = votes
        result['vVotingPairs'] = vVotingPairs

        return result


    def matchStarsToTx(self, df_ref: pd.DataFrame, df_tgt: pd.DataFrame, 
                   vertex_sorted = True,
                   limit_ref_triangle_fov=None):
        """ matchStars in a reference and target dataframes from either database or a photo
            Adds columns to target dataframe: starno (index in reference dataframe) and votes (int)
            Returns a transform from df to tgt
            Code developed in refine_location3.ipynb
        """
        result = {
            'vertex_sorted': vertex_sorted,
            'limit_ref_triangle_fov': limit_ref_triangle_fov
        }

        if vertex_sorted:
            # tri_ref = self._getVertexSortedTriangles(df_ref, combinations(df_ref.index, 3), fov_deg=limit_ref_triangle_fov)
            tri_ref = pd.DataFrame(self._getVertexSortedDelaunayTriangles(df_ref, fov_deg=limit_ref_triangle_fov))
            tri_tgt = pd.DataFrame(self._getVertexSortedTriangles(df_tgt, combinations(df_tgt.index, 3), fov_deg=None))
        else:
            tri_ref = self._getTriangles(df_ref)
            tri_tgt = self._getTriangles(df_tgt)

        # print(f"Ref triangles: {len(tri_ref)}, Tgt triangles: {len(tri_tgt)}")
        result['ref_triangles'] = len(tri_ref)
        result['tgt_triangles'] = len(tri_tgt)

        TRIANGLETOLERANCE = 1e-2
        txs = []
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
                src = np.stack([ra, rb, rc]).astype(np.float32)
                dst = np.stack([ta, tb, tc]).astype(np.float32)
                tx = cv2.getAffineTransform(src, dst)
                mapped = False
                for i, (e,c) in enumerate(txs):
                    if np.linalg.norm(tx - e) < 10000:
                        txs[i][1] += 1
                        mapped = True
                        # print(tx,r.A, r.B, r.C, tgt.A, tgt.B, tgt.C)
                        break
                if not mapped:
                    txs.append([tx, 1])

        tx, num_max_matches = sorted(txs, key=lambda x: x[1], reverse=True)[0]
        result["matches"] = num_max_matches
        return tx, result



    def _getTriangles(self, df):
        """ Return pair of side-ratios for each triangle formed by permutations of stars
        For each triangle ABC, with side lengths a,b,c in asc order (c is longest)
        return (a/c, b/c); sorted by a/c
        """
        # Cache distances between every pair of stars
        starDistances = {}
        for c in combinations(df.index, 2):
            assert(c[1] > c[0])
            key = (c[0], c[1])
            x1, y1 = df.loc[c[0],['cluster_cx', 'cluster_cy']]
            x2, y2 = df.loc[c[1],['cluster_cx', 'cluster_cy']]
            starDistances[key] = math.sqrt((x2-x1)**2 + (y2-y1)**2)

        vTriangles = []
        for i,j,k in combinations(df.index, 3):
            vDistances = sorted([starDistances[(i,j)], starDistances[(j,k)], starDistances[(i,k)]])

            if vDistances[2] > 0:
                fX = vDistances[1]/vDistances[2]
                fY = vDistances[0]/vDistances[2]

                # Add to the triangle list
                vTriangles.append({"s1":i, "s2":j, "s3":k, "fX":fX, "fY":fY})

        vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
        return pd.DataFrame(vTriangles)


    def _getVertexSortedDelaunayTriangles(self, df_ref, fov_deg=None):
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
                if len(df) < 3: continue
                pt_indices = []
                for x, y, z in D.simplices:
                    a, b, c = pt_idx[x], pt_idx[y], pt_idx[z]
                    if (a,b,c) not in added_triangles:
                        added_triangles.add((a, b, c))
                        pt_indices.append([a, b, c])
                vTriangles.extend(self._getVertexSortedTriangles(df_ref, pt_indices, fov_deg=fov_deg))

        # output triangles sorted by fX
        vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
        return vTriangles


    def _getVertexSortedTriangles(self, df, simplices, fov_deg=None, cache_distances=False):

        if cache_distances:
            # Cache distances between every pair of stars
            starDistances = {}
            for c in combinations(df.index, 2):
                assert(c[1] > c[0])
                key = (c[0], c[1])
                x1, y1 = df.loc[c[0],['cluster_cx', 'cluster_cy']]
                x2, y2 = df.loc[c[1],['cluster_cx', 'cluster_cy']]

                if fov_deg:
                    ra1, dec1 = df.loc[c[0],['ra', 'dec']]
                    ra2, dec2 = df.loc[c[1],['ra', 'dec']]
                    sphere_dist = math.sqrt((ra2-ra1)**2 + (dec2-dec1)**2)
                else:
                    sphere_dist = None

                cartesian_dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                starDistances[key] = cartesian_dist, sphere_dist

        def starDistance(df, i, j, fov_deg):
            if fov_deg:
                ra1, dec1 = df.loc[i,['ra', 'dec']]
                ra2, dec2 = df.loc[j,['ra', 'dec']]
                sphere_dist = math.sqrt((ra2-ra1)**2 + (dec2-dec1)**2)
            else:
                sphere_dist = None
            x1, y1 = df.loc[i,['cluster_cx', 'cluster_cy']]
            x2, y2 = df.loc[j,['cluster_cx', 'cluster_cy']]
            cartesian_dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            return cartesian_dist, sphere_dist

        vTriangles = []
        for i,j,k in simplices:

            if cache_distances:
                ij, ijam = starDistances[(i, j)]
                jk, jkam = starDistances[(j, k)]
                ik, ikam = starDistances[(i, k)]
            else:
                # edge distances
                ij, ijam = starDistance(df, i, j, fov_deg)
                jk, jkam = starDistance(df, j, k, fov_deg)
                ik, ikam = starDistance(df, i, k, fov_deg)

            # filter out triangles with edges longer than fov
            # TODO: better to avoid iterating these combinations
            if fov_deg and (ijam > fov_deg or
               jkam > fov_deg or
               ikam > fov_deg):
                continue

            # sort edges by length
            s, m, l = sorted([
                (set([i, j]), ij),
                (set([j, k]), jk),
                (set([i, k]), ik)
            ], key=lambda x:x[1])

            # sorted vertices
            # AC: longest side, AB: shortest side
            A = s[0].intersection(l[0]).pop()
            C = m[0].intersection(l[0]).pop()
            B = s[0].intersection(m[0]).pop()

            # ratio of smallest & mid to longest
            fX = s[1]/l[1]
            fY = m[1]/l[1]

            # Add to the triangle list
            vTriangles.append({"A":A, "B":B, "C":C, "fX":fX, "fY":fY})

        # output triangles sorted by fX
        vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
        return vTriangles

def register_stars(image_fnames):
    """ Register stars across image frames
    Input: list of image file names
    Output: List of stars that occur in all frames. For each star, a list of occurances in each frame is returned.
    """
    starFinder = StarFinder()
    matcher = StarMatcher()

    star_frames = []
    df = None
    for fname in image_fnames:
        starData = starFinder.getStarData(fname)['stars']
        if df is None:
            df = starData
            df['starno'] = None
        else:
            matcher.matchStars(df, starData, vertex_sorted=False)
            df = starData[starData.starno.notnull()]
        star_frames.append(df)
        df = df.reset_index()

    star_paths = defaultdict(list)
    for i in range(len(star_frames[-1])):
        starno = i
        for frame in star_frames[::-1]:
            star = frame.iloc[starno]
            star_paths[i].append(star)
            starno = star.starno

    return [path[::-1] for _, path in star_paths.items()]


if __name__ == "__main__":
    from star_finder import StarFinder
    out_of_focus = r"C:\code\astrocam\outoffocus\Image741.nef"
    in_focus = r"C:\code\astrocam\light\Image752.nef"
    s = StarFinder()

    ref_data = s.getStarData(in_focus)
    tgt_data = s.getStarData(out_of_focus)
    ref_image, df_ref = ref_data["image"], ref_data["stars"]
    tgt_image, df_tgt = tgt_data["image"], tgt_data["stars"]

    matcher = StarMatcher()
    df_matched = matcher.matchStars(df_ref, df_tgt)
    print(df_matched.head())
