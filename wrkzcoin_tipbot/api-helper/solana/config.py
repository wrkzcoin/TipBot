from toml import load

def load_config():
    with open("../../config.toml") as f:
        return load(f)
