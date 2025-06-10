import os

def _create_log_file_path(log_dir: str, log_filename: str) -> str:
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, log_filename)