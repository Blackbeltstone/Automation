import os
from pathlib import Path
import shutil  # Imported shutil for copying if needed

# Define folder paths
# BASE_DIR is updated to a relative path suitable for Windows
BASE_DIR = Path("data")
DATA_DUMP = BASE_DIR / "01_DataDump"
ARCHIVE = BASE_DIR / "02_Archive"
PROCESSING = BASE_DIR / "03_Processing"
PROCESSED = BASE_DIR / "04_Processed"
PROCESSED_PANOS = PROCESSED / "Pano_Scans"
PROCESSED_3D = PROCESSED / "3D_Viewers"
UPLOADED = BASE_DIR / "05_Uploaded"
VIDEOS_NEED_PROCESSED = BASE_DIR / "06_VideosNeedProcessed"
UPLOADED_3D = BASE_DIR / "07_Uploaded_3D"
ZZZ_360_TOOLS = BASE_DIR / "zzz_360_TOOLS"
TRACKING_SHEET = BASE_DIR / "TREKK360_Tracking.xlsx"

# Folder setup functions
def setup_folders():
    """
    Ensure all necessary folders exist.
    """
    folders = [
        DATA_DUMP, ARCHIVE, PROCESSING, PROCESSED, PROCESSED_PANOS,
        PROCESSED_3D, UPLOADED, VIDEOS_NEED_PROCESSED, UPLOADED_3D, ZZZ_360_TOOLS
    ]
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            print(f"Ensured folder exists: {folder}")
        except Exception as e:
            print(f"Error creating folder {folder}: {e}")

# Project and structure creation functions
def create_project_root(data_dump, project_number, collection_date, crew_initials):
    """
    Create the root directory for a project.
    """
    root_folder_name = f"{project_number}_{collection_date}_{crew_initials}"
    root_folder = data_dump / root_folder_name
    root_folder.mkdir(parents=True, exist_ok=True)
    return root_folder

def create_structure_folder(root_folder, project_location, structure_id, collection_date):
    """
    Create a structure folder within a project.
    """
    structure_folder_name = f"{project_location}_{structure_id}_{collection_date}"
    structure_folder = root_folder / structure_folder_name
    structure_folder.mkdir(parents=True, exist_ok=True)
    return structure_folder

# Photo organization function
def organize_photos(data_dump, root_folder, photos, project_location, structure_id, collection_date):
    """
    Organize photos into the appropriate structure folder.
    """
    structure_folder = root_folder / f"{project_location}_{structure_id}_{collection_date}"
    structure_folder.mkdir(parents=True, exist_ok=True)

    for photo in photos:
        new_path = structure_folder / photo.name
        photo.rename(new_path)
        yield str(new_path.relative_to(data_dump))

# Archiving functions
def archive_files(data_dump, archive_dir):
    """
    Archive all files from Data Dump to Archive.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    for file in data_dump.iterdir():
        if file.is_file():
            destination = archive_dir / file.name
            file.rename(destination)
            print(f"Archived {file} to {destination}")

def archive_project_files(data_dump: Path, archive_dir: Path, project_folder_name: str):
    """
    Move a project directory from Data Dump to Archive.
    """
    source = data_dump / project_folder_name
    destination = archive_dir / project_folder_name
    if source.exists() and source.is_dir():
        try:
            shutil.move(str(source), str(destination))  # Use shutil.move to handle directories
            print(f"Archived '{source}' to '{destination}'")
        except Exception as e:
            print(f"Error archiving directory '{source}': {e}")
            raise e
    else:
        error_msg = f"Directory '{source}' does not exist."
        print(error_msg)
        raise FileNotFoundError(error_msg)

# File movement function
def move_file(source_path: Path, destination_path: Path):
    """
    Move a file from source_path to destination_path.
    """
    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(destination_path)
        print(f"Moved {source_path} to {destination_path}")
    except Exception as e:
        print(f"Error moving file from {source_path} to {destination_path}: {e}")


