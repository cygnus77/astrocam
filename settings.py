import yaml
import os

with open(os.path.join(os.path.dirname(__file__),'config.yml'), 'r') as f:
    config = yaml.safe_load(f)

