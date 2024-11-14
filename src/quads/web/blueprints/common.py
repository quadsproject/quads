import os

from quads.config import Config

WEB_CONTENT_PATH = Config.get("web_content_path")
EXCLUDE_DIRS = Config.get("web_exclude_dirs")


def get_file_paths(web_path: str = WEB_CONTENT_PATH):
    file_paths = []
    for _, dirs, files in os.walk(web_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_paths.append(file)
    return file_paths
