import requests
from tqdm import tqdm
import numpy as np
from urllib.parse import quote

root_url = """https://simbad.u-strasbg.fr/simbad/sim-sam"""

cookie = "H4sIAAAAAAAAAD1QwW6DMBT7liftRpEIUGl7t46tFdvaw6gm7QgJEUyBMEgR3dfPKdoukWM7L8+2VUBmCqhXXJAZAhpnGZA2TFbGIQ4BvbWc7c5veXGGPAdUOSjwVrDaTvGerPYvFejJU5C+MKHG2yUkp/iDpBI8xSQnTJUqXnHiceLxOP8E1PChdmBSVl4V/v8U8yR89XfKcRRFAOIPxCuQ3eD1hMXDNiJtmYwqQzId1jRVSFXDO2PIzLj2uF4Fi3s4bY89rzHfycs41r37rMuRbIkPMWNXZHlOtsFtQQywxsGuuGqr/tKRTnj/mpJBcJ3yoTSkBefZe0HW2ZB0DHlLeuEU41oQfhkUYxqkQoemk/zUTq7sZY2GQdyids4fyy1YBF7ycXM6ZJvT7vgMCyoxMvFm1FgPKb+sVQwJP97S10P8z4kV/QKr+8Ch4wEAAA=="

def sweep_faint_objects():
  step_size = 0.25 # RAH
  mag_limit = 11
  for segid, ra in tqdm(enumerate(np.arange(0, 24, step_size))):
    for hemisphere,dec_cond in [("nh", "dec>=0"), ("sh", "dec<0")]:
      with open(f"simbad_{hemisphere}_{segid}.txt", "wt", encoding='utf-8') as f:

        resp = requests.get(root_url, cookies={"simbadOptions": cookie}, params={
          "Criteria": f"{dec_cond}&rah>={ra}&rah<{ra+step_size}&(cat='NGC'|Vmag<{mag_limit})",
          "submit": "submit%20query",
          "OutputMode": "LIST",
          "maxObject": "20000",
          "output.format": "ASCII",
        })
        if resp.status_code == 200:
          f.write(resp.text)
        else:
          print(f"Error with ra: {ra}!")

def get_all_M():
  with open(f"simbad_M.txt", "wt", encoding='utf-8') as f:

    resp = requests.get(root_url, cookies={"simbadOptions": cookie}, params={
      "Criteria": f"cat='M'",
      "submit": "submit%20query",
      "OutputMode": "LIST",
      "maxObject": "20000",
      "output.format": "ASCII",
    })
    if resp.status_code == 200:
      f.write(resp.text)

if __name__ == "__main__":
  get_all_M()