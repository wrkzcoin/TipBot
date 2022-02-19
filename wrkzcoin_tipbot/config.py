import os

import yaml
from munch import Munch

config_file_path = os.path.join(
    os.path.dirname(__file__), 'config.yml')

config = None


def load_config():
    with open(config_file_path) as config_file:
        _config = yaml.safe_load(config_file)
        globals()['config'] = Munch.fromDict(_config)


load_config()

