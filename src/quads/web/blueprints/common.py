import os
import re

from quads.config import Config

INSTACK_FILE_RE = re.compile(r"^(?P<cloud>.+?)_(?:instackenv|ocpinventory)\.json(?:_.+)?$")


def extract_cloud_from_instack_file(filename: str):
    match = INSTACK_FILE_RE.match(filename)
    return match.group("cloud") if match else None


WEB_CONTENT_PATH = Config.get("web_content_path")
EXCLUDE_DIRS = Config.get("web_exclude_dirs")


def get_file_paths(web_path: str = WEB_CONTENT_PATH):
    file_paths = []
    for _, dirs, files in os.walk(web_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_paths.append(file)
    return file_paths
