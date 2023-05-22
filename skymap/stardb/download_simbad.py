import requests
from tqdm import tqdm
import numpy as np

query_template = """https://simbad.u-strasbg.fr/simbad/sim-sam?Criteria=Vmag%3c{0}%26dec%20%20%20%3e-30%26rah%3e%3d{1}%26rah%3c{2}&submit=submit%20query&OutputMode=LIST&maxObject=20000&CriteriaFile=&output.format=ASCII"""

cookie = "H4sIAAAAAAAAAD1Ry26DMBD8lpV6I0jYEKndG0FtRB85lKhST1XwQ6EymAJBab++Y1B7sWZn1uOdta9jcmNEneaKXB/TMKuIrGPySsY4RESu8Vzkx+eyOkKeI6onKOit0epbzQfyNoKkQY+BgvQJBwPva0yT5jdSWvAoSY1wVVquOA04DXiYfyI6895MYDLWQRXh/Qx+Cn3mK2OZJAmA+ANyBartg56yuNsmZD2T0yc83WJMh3z1mXPnyM0oO5TfgsUtOv1SSL5Rl2Ew3fRuTgN53PTwyKuiLD+O+Y78GQxiuOA5Ib3muqm7S0s25YenjBzC24z3J0dWcFm8VuQnH5OVkLdkr5zBsgERBsJyXHAM07QKszbY8BIzzOvb6xIqAa/4ZXPYF5tD/nKPFqzDhU248DGmz/hxXUOf8m5Jbnr5z4kV/QKiiDab3wEAAA=="

if __name__ == "__main__":
  step_size = 0.25 # RAH
  mag_limit = 11
  for segid, ra in tqdm(enumerate(np.arange(0, 24, step_size))):
    if segid < 78:
      continue
    with open(f"simbad_data_{segid}.vot", "wt", encoding='utf-8') as f:
      url = query_template.format(mag_limit, ra, ra+step_size)
      resp = requests.get(url, cookies={"simbadOptions": cookie})
      if resp.status_code == 200:
        f.write(resp.text)
      else:
        print(f"Error with ra: {ra}!")
