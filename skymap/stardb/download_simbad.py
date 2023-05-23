import requests
from tqdm import tqdm
import numpy as np
from urllib.parse import quote

query_template = """https://simbad.u-strasbg.fr/simbad/sim-sam"""

cookie = "H4sIAAAAAAAAAD1R0U6DQBD8lk18oyTcQRPdNyTaoLYPYkx8hDtIMQuHQEn1652D6AuZnV1mZ/ZcFZJMAfWWC5IhoHExATXC5IwO8VEBSes4S99e8uIN7SWgakYHsxVGXWf5RK7xf1rQk6dCqj6hUEP7GtJs+Z2MVTxpMhNUjdUbjj2OPR6Xn4DOfKhnMAlb31V+fwI9g7n6K2EdRRGA+gN6A6YbfD9mdbePqHFMYkus7mBTkK86cypCsqDsUX4rVreYdGuh+cZcxrHu54+6HMmVWAiNtMjynNwZHhBBwMqMxJartuovHTUxPz4nJAjeJHwohRrFefZakJtdSI1Ge0/NlRPItSC8GRxGvKJ30hn4bCG7RvReXXddA0XgDR93p0O2O6XHB4zgFOKvIP5R6iHhp+0EQ8z3a+p60P+c2tAvpH38cdsBAAA="

if __name__ == "__main__":
  step_size = 0.25 # RAH
  mag_limit = 11
  for segid, ra in tqdm(enumerate(np.arange(0, 24, step_size))):
    for hemisphere,dec_cond in [("nh", "dec>=0"), ("sh", "dec<0")]:
      with open(f"simbad_{hemisphere}_{segid}.txt", "wt", encoding='utf-8') as f:
        url = query_template.format(mag_limit, ra, ra+step_size)
        resp = requests.get(url, cookies={"simbadOptions": cookie}, params={
          "Criteria": f"Vmag<{mag_limit}&{dec_cond}&rah>={ra}&rah<{ra+step_size}",
          "submit": "submit%20query",
          "OutputMode": "LIST",
          "maxObject": "20000",
          "output.format": "ASCII",
        })
        if resp.status_code == 200:
          f.write(resp.text)
        else:
          print(f"Error with ra: {ra}!")
