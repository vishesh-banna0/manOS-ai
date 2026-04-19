from pathlib import Path
from fastapi import UploadFile


# 👉 FIXED: now points to Manos AI root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

BASE_DATA_PATH = BASE_DIR / "data" / "instances"


def save_file(instance_id: int, file: UploadFile) -> str:
    """
    Save uploaded file to instance-specific folder.

    Returns:
        file_path (str)
    """

    instance_path = BASE_DATA_PATH / str(instance_id)
    instance_path.mkdir(parents=True, exist_ok=True)

    file_path = instance_path / file.filename

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return str(file_path)