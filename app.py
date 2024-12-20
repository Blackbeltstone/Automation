from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, BackgroundTasks, File  # Added File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import os  # Import os for file operations
from folder_manager import (
    create_project_root,
    organize_photos,
    archive_files,
    archive_project_files,  # Ensure archive_project_files is imported
    setup_folders  # Imported setup_folders
)
from db_manager import (
    insert_project,
    insert_structure,
    insert_file,
    get_all_projects,
    get_structures_by_project,
    get_structure_by_id,
    get_files_by_structure,
    get_project_by_id,
    get_projects_with_sites_and_dates,
    get_files_by_structure_and_date,
)
from fastapi.staticfiles import StaticFiles
from typing import List, Dict  # Added Dict to imports 
import sqlite3
import subprocess

app = FastAPI()

templates = Jinja2Templates(directory="templates")

DATA_DUMP = Path("data/01_DataDump")
ARCHIVE_DIR = Path("data/02_Archive")
PROCESSING_DIR = Path("data/03_Processing")  # Define Processing directory
PROCESSED_DIR = Path("data/04_Processed")  # Define Processed directory
TOOLS_DIR = Path("data/zzz_360_TOOLS")
POWERSHELL_SCRIPT = TOOLS_DIR / "ProcessPan2vrImages.ps1"
P2VR_TEMPLATE = TOOLS_DIR / "panosettings.p2vr"

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")

# Ensure all folders are created on startup
def setup_all_folders():
    setup_folders()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

setup_all_folders()

@app.post("/upload/")
async def upload_files(
    request: Request,
    project_number: str = Form(...),
    collection_date: str = Form(...),
    crew_initials: str = Form(...),
    project_location: str = Form(...),
    structure_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    try:
        # Debugging output for files
        for file in files:
            print(f"DEBUG: Uploading file: {file.filename}")

        # Insert project and structure
        project_id = insert_project(project_number, collection_date, crew_initials)
        structure_db_id = insert_structure(project_id, project_location, structure_id, collection_date)
        print(f"DEBUG: Project ID: {project_id}, Structure DB ID: {structure_db_id}")

        # File handling
        parent_folder = Path(f"data/01_DataDump/{project_number}_{collection_date}_{crew_initials}")
        parent_folder.mkdir(parents=True, exist_ok=True)
        child_folder = parent_folder / f"{project_location}_{structure_id}_{collection_date}"
        child_folder.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        for file in files:
            file_path = child_folder / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(file_path)

            # Insert file record into the database
            file_id = insert_file(structure_db_id, file.filename, str(file_path))
            print(f"DEBUG: Inserted file ID: {file_id}")

        # Return confirmation
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "uploaded_files": [str(file.relative_to("data")) for file in uploaded_files],
                "project_folder": parent_folder.name,
                "child_folder": child_folder.name,
            },
        )
    except sqlite3.Error as db_error:
        print(f"Database error during file upload: {db_error}")
        raise HTTPException(status_code=500, detail="Database Error")
    except OSError as os_error:
        print(f"File system error during file upload: {os_error}")
        raise HTTPException(status_code=500, detail="File System Error")
    except Exception as e:
        print(f"Unexpected error during file upload: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        # Ensure all file objects are closed
        for file in files:
            try:
                file.file.close()
            except Exception as e:
                print(f"Error closing file: {file.filename}. Error: {e}")

    
@app.get("/", response_class=HTMLResponse)
async def list_projects(request: Request):
    try:
        # Initialize hierarchical structure: step -> upper_dir -> lower_dir -> files
        files_by_step = {}
        steps = [
            "01_DataDump",
            "02_Archive",
            "03_Processing",
            "04_Processed",
            "05_Uploaded",
            "06_VideosNeedProcessed",
            "07_Uploaded_3D",
            "zzz_360_TOOLS"  # Updated to match the actual folder name
        ]

        for step in steps:
            step_path = Path(f"data/{step}")  # Removed replace(' ', '_')

            files_by_step[step] = {}

            if not step_path.exists():
                print(f"Warning: Step folder '{step_path}' does not exist.")
                continue  # Skip if the step folder doesn't exist to prevent errors

            for upper_dir in step_path.iterdir():
                if upper_dir.is_dir():
                    upper_dir_name = upper_dir.name
                    files_by_step[step][upper_dir_name] = {}

                    for lower_dir in upper_dir.iterdir():
                        if lower_dir.is_dir():
                            lower_dir_name = lower_dir.name
                            files = []

                            for file in lower_dir.glob("**/*"):
                                if file.is_file():
                                    relative_path = file.relative_to("data").as_posix()
                                    files.append({
                                        "filename": file.name,
                                        "path": relative_path
                                    })

                            files_by_step[step][upper_dir_name][lower_dir_name] = files

        print("DEBUG: Successfully collected files by step")
        return templates.TemplateResponse("projects.html", {
            "request": request,
            "files_by_step": files_by_step  # Pass hierarchical files grouped by step, upper and lower directories
        })
    except Exception as e:
        print(f"Error in list_projects: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/structures/{structure_db_id}/photos/{collection_date}", response_class=HTMLResponse)
async def list_photos(request: Request, structure_db_id: int, collection_date: str):
    # Fetch photos for the structure and collection date
    files = get_files_by_structure_and_date(structure_db_id, collection_date)

    if not files:
        raise HTTPException(status_code=404, detail="No photos found for this date.")

    # Debugging: Print fetched files
    print(f"DEBUG: Retrieved files for structure_db_id={structure_db_id}, collection_date={collection_date}:", files)

    return templates.TemplateResponse(
        "photos.html",
        {
            "request": request,
            "files": files,
            "structure_db_id": structure_db_id,
            "collection_date": collection_date,
        },
    )

@app.post("/projects/")
async def create_project(project_number: str = Form(...), date: str = Form(...), crew_initials: str = Form(...)):
    project_id = insert_project(project_number, date, crew_initials)
    return {"message": "Project created successfully", "project_id": project_id}

@app.get("/projects/{project_id}/structures", response_class=HTMLResponse)
async def list_structures(request: Request, project_id: int):
    structures = get_structures_by_project(project_id)
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse("structures.html", {"request": request, "structures": structures, "project": project})

@app.post("/structures/")
async def create_structure(
    project_id: int = Form(...), project_location: str = Form(...), structure_id: str = Form(...), collection_date: str = Form(...)
):
    structure_db_id = insert_structure(project_id, project_location, structure_id, collection_date)
    return {"message": "Structure created successfully", "structure_db_id": structure_db_id}

@app.get("/structures/{structure_db_id}/files", response_class=HTMLResponse)
async def list_files(request: Request, structure_db_id: int):
    files = get_files_by_structure(structure_db_id)
    structure = get_structure_by_id(structure_db_id)  # Fetch structure data

    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")

    return templates.TemplateResponse(
        "files.html",
        {
            "request": request,
            "files": files,
            "structure": {
                "structure_id": structure["structure_id"],  # Use structure_id field for display
                "project_id": structure["project_id"],
            },
        },
    )

@app.post("/files/")
async def create_file(structure_db_id: int = Form(...), filename: str = Form(...), path: str = Form(...)):
    file_id = insert_file(structure_db_id, filename, path)
    return {"message": "File added successfully", "file_id": file_id}

@app.get("/upload/", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload_form.html", {"request": request})

@app.post("/archive/")
async def archive_datadump(request: Request):
    archive_files(DATA_DUMP, ARCHIVE_DIR)
    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": "success",
            "message": "All files archived successfully."
        },
    )

@app.post("/archive_project/")
async def archive_project(request: Request, project_folder_name: str = Form(...)):
    """
    Archive a specific project by moving it from Data Dump to Archive.
    """
    try:
        archive_project_files(DATA_DUMP, ARCHIVE_DIR, project_folder_name)
        message = f"Project '{project_folder_name}' archived successfully."
        status = "success"
    except FileNotFoundError as fnf_error:
        message = str(fnf_error)
        status = "error"
    except Exception as e:
        message = f"An unexpected error occurred: {e}"
        status = "error"

    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": status,
            "message": message
        },
    )

@app.post("/archive_data_dump/")
async def archive_data_dump(request: Request, directory: str = Form(...)):
    """
    Archive a specified directory from Data Dump to Archive.
    """
    try:
        archive_project_files(DATA_DUMP, ARCHIVE_DIR, directory)
        message = f"Directory '{directory}' archived successfully."
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "message": message
            },
        )
    except Exception as e:
        print(f"Error archiving directory '{directory}': {e}")
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "error",
                "message": f"Failed to archive directory '{directory}'. Please try again."
            },
        )

def archive_files_single(file_path):
    """
    Move a single file from Data Dump to Archive.
    """
    source = DATA_DUMP / file_path
    destination = ARCHIVE_DIR / file_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    print(f"Archived {source} to {destination}")

@app.post("/archive_file/")
async def archive_file(request: Request, file_path: str):
    """
    Archive a single file by moving it from Data Dump to Archive.
    """
    archive_files_single(file_path)
    return {"message": "File archived successfully."}

# New endpoints for each folder/step

def collect_files(directory: Path) -> Dict[str, Dict[str, list]]:
    """
    Helper function to traverse the given directory and collect files grouped by project and site.
    """
    files_by_project = {}
    
    if not directory.exists():
        print(f"Directory {directory} does not exist.")
        return files_by_project
    
    for project_dir in directory.iterdir():
        if project_dir.is_dir():
            project_name = project_dir.name
            files_by_project[project_name] = {}
            project_files = []
    
            for item in project_dir.iterdir():
                if item.is_dir():
                    site_name = item.name
                    files = []
    
                    for file in item.glob("*"):
                        if file.is_file():
                            relative_path = file.relative_to("data").as_posix()
                            files.append({
                                "filename": file.name,
                                "path": relative_path
                            })
    
                    files_by_project[project_name][site_name] = files
                elif item.is_file():
                    # Collect files directly under the project directory
                    relative_path = item.relative_to("data").as_posix()
                    project_files.append({
                        "filename": item.name,
                        "path": relative_path
                    })
                else:
                    print(f"Skipping unknown item in project level: {item}")
    
            if project_files:
                # Use an empty string as the key for files without a site
                files_by_project[project_name][""] = project_files
    
        else:
            print(f"Skipping non-directory in project level: {project_dir}")
    
    # Debugging output
    print(f"Collected files in {directory}: {files_by_project}")
    return files_by_project

@app.get("/{step}/", response_class=HTMLResponse)
async def view_step(request: Request, step: str):
    """
    Generic endpoint to display files in the specified step directory grouped by project and site.
    """
    try:
        step_mapping = {
            "data_dump": DATA_DUMP,
            "archive": ARCHIVE_DIR,
            "processing": PROCESSING_DIR,
            "processed": PROCESSED_DIR,
            "uploaded": Path("data/05_Uploaded"),
            "videos_need_processed": Path("data/06_VideosNeedProcessed"),
            "uploaded_3d": Path("data/07_Uploaded_3D"),
            "360_tools": Path("data/zzz_360_TOOLS")  # Updated to match the actual folder name
        }

        directory = step_mapping.get(step.lower())
        if not directory:
            raise HTTPException(status_code=404, detail="Step not found.")

        # Debugging output
        print(f"Accessing step '{step}' with directory '{directory}'")

        files_by_project = collect_files(directory)

        template_mapping = {
            "data_dump": "data_dump.html",
            "archive": "archive.html",
            "processing": "processing.html",
            "processed": "processed.html",
            "uploaded": "uploaded.html",
            "videos_need_processed": "videos_need_processed.html",
            "uploaded_3d": "uploaded_3d.html",
            "360_tools": "360_tools.html"
        }

        template_name = template_mapping.get(step.lower(), "confirmation.html")

        print(f"DEBUG: Successfully collected files for step '{step}'")
        return templates.TemplateResponse(template_name, {
            "request": request,
            "files_by_project": files_by_project  # Pass hierarchical files grouped by project and site
        })
    except Exception as e:
        print(f"Error in view_step: {e}")
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "error",
                "message": f"Failed to load {step.replace('_', ' ').title()}. Please try again later."
            },
        )

@app.post("/archive_action/")
async def archive_action(request: Request, directory: str = Form(...)):
    """
    Archive a specific directory from Data Dump to Archive.
    """
    try:
        archive_project_files(DATA_DUMP, ARCHIVE_DIR, directory)
        message = f"Directory '{directory}' archived successfully."
        status = "success"
    except FileNotFoundError as fnf_error:
        message = str(fnf_error)
        status = "error"
    except Exception as e:
        message = f"An unexpected error occurred: {e}"
        status = "error"

    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": status,
            "message": message
        },
    )

@app.post("/copy_to_processing/")
async def copy_to_processing(request: Request, directory: str = Form(...)):
    """
    Copy a specific directory from Archive to Processing without removing it from Archive.
    """
    source = ARCHIVE_DIR / directory
    destination = PROCESSING_DIR / directory

    if not source.exists() or not source.is_dir():
        message = f"Directory '{source}' does not exist in Archive."
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "error",
                "message": message
            },
        )
    
    if destination.exists():
        message = f"Directory '{directory}' already exists in Processing."
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "error",
                "message": message
            },
        )
    
    try:
        shutil.copytree(source, destination)
        message = f"Directory '{directory}' has been copied to Processing successfully."
        status = "success"
    except Exception as e:
        message = f"Failed to copy directory '{directory}' to Processing. Error: {e}"
        status = "error"
    
    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": status,
            "message": message
        },
    )

@app.post("/process_file/")
async def process_file(request: Request, file_path: str = Form(...)):
    """
    Process a specific file by moving it from Processing to Processed.
    """
    source = Path("data/03_Processing") / file_path
    destination = PROCESSED_DIR / file_path

    if not source.exists() or not source.is_file():
        message = f"File '{source}' does not exist in Processing."
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "error",
                "message": message
            },
        )
    
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.move(str(source), str(destination))
        message = f"File '{file_path}' has been processed and moved to Processed successfully."
        status = "success"
    except Exception as e:
        message = f"Failed to process file '{file_path}'. Error: {e}"
        status = "error"
    
    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": status,
            "message": message
        },
    )

@app.post("/move_to_processing/")
async def move_to_processing(request: Request, directory: str = Form(...)):
    """
    Move a specific directory from Archive to Processing and delete all .mp4 files in Processing.
    """
    try:
        source = ARCHIVE_DIR / directory
        destination = PROCESSING_DIR / directory

        if not source.exists() or not source.is_dir():
            message = f"Directory '{source}' does not exist in Archive."
            status = "error"
            return templates.TemplateResponse(
                "confirmation.html",
                {
                    "request": request,
                    "status": status,
                    "message": message
                },
            )

        if destination.exists():
            message = f"Directory '{directory}' already exists in Processing."
            status = "error"
            return templates.TemplateResponse(
                "confirmation.html",
                {
                    "request": request,
                    "status": status,
                    "message": message
                },
            )

        # Copy the directory from Archive to Processing
        shutil.copytree(source, destination)
        print(f"Copied '{source}' to '{destination}'")

        # Traverse the Processing directory and delete all .mp4 files
        for root, dirs, files in os.walk(destination):
            for file in files:
                if file.lower().endswith('.mp4'):
                    file_path = Path(root) / file
                    try:
                        file_path.unlink()  # Delete the file
                        print(f"Deleted video file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file '{file_path}': {e}")

        message = f"Directory '{directory}' has been moved to Processing and all .mp4 files have been deleted."
        status = "success"

    except Exception as e:
        print(f"Error moving directory '{directory}' to Processing: {e}")
        message = f"Failed to move directory '{directory}' to Processing. Error: {e}"
        status = "error"

    return templates.TemplateResponse(
        "confirmation.html",
        {
            "request": request,
            "status": status,
            "message": message
        },
    )

@app.post("/process_images/")
async def process_images(request: Request, directory: str = Form(...)):
    """
    Process images in the specified directory using the PowerShell script.
    """
    try:
        # Define source and destination directories
        source = PROCESSING_DIR / directory
        destination = PROCESSED_DIR / directory

        # Check if the source directory exists
        if not source.exists() or not source.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Source directory '{source}' does not exist in Processing."
            )

        # Run the PowerShell script
        process = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(TOOLS_DIR / "ProcessPan2vrImages.ps1"),
                str(source),
                str(destination),
            ],
            capture_output=True,
            text=True,
        )

        # Handle errors in the PowerShell script
        if process.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"PowerShell script failed with error: {process.stderr}"
            )

        # Return success confirmation
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "message": f"Directory '{directory}' processed successfully.",
                "output": process.stdout,
            },
        )
    except Exception as e:
        print(f"Error processing images: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during image processing: {e}"
        )

# PowerShell Script Execution Route
@app.post("/run_powershell/")
async def run_powershell(
    request: Request,
    processing_path: str = Form(...),
    p2vr_file: str = Form(...),
):
    try:
        # Full paths
        processing_folder = Path(processing_path)
        p2vr_template_file = Path(p2vr_file)

        if not processing_folder.exists() or not p2vr_template_file.exists():
            raise HTTPException(
                status_code=400, detail="Processing folder or P2VR file does not exist."
            )

        # Run PowerShell Script
        process = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(POWERSHELL_SCRIPT),
                str(processing_folder),
                str(p2vr_template_file),
            ],
            capture_output=True,
            text=True,
        )

        # Capture output
        if process.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"PowerShell script failed with error: {process.stderr}",
            )

        # Return success message with output
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "message": "PowerShell script executed successfully.",
                "output": process.stdout,
            },
        )
    except Exception as e:
        print(f"Error executing PowerShell script: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# Endpoint to handle copying to processing and running the PowerShell script
@app.post("/process_trekk360/")
async def process_trekk360(request: Request, directory: str = Form(...)):
    try:
        source = ARCHIVE_DIR / directory
        destination = PROCESSING_DIR / directory

        if not source.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Source directory '{source}' does not exist in Archive.",
            )

        # Copy to Processing folder
        shutil.copytree(source, destination, dirs_exist_ok=True)
        print(f"Copied '{source}' to '{destination}'")

        # Execute PowerShell script
        process = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(POWERSHELL_SCRIPT),
                str(destination),
                str(P2VR_TEMPLATE),
            ],
            capture_output=True,
            text=True,
        )

        # Handle PowerShell output
        if process.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"PowerShell script failed with error: {process.stderr}",
            )

        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "message": f"Directory '{directory}' processed successfully.",
                "output": process.stdout,
            },
        )
    except Exception as e:
        print(f"Error processing TREKK360 files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during processing: {e}",
        )
    
@app.get("/processing/", response_class=HTMLResponse)
async def view_processing(request: Request):
    """
    List all projects in the Processing folder with a process button for each.
    """
    try:
        projects = [folder.name for folder in PROCESSING_DIR.iterdir() if folder.is_dir()]
        return templates.TemplateResponse(
            "processing.html",
            {
                "request": request,
                "projects": projects,
            },
        )
    except Exception as e:
        print(f"Error listing projects in Processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to load processing projects.")

@app.post("/process_project/")
async def process_project(request: Request, project_name: str = Form(...)):
    """
    Process a specific project in the Processing folder using the PowerShell script.
    """
    try:
        source = PROCESSING_DIR / project_name
        destination = PROCESSED_DIR / project_name
        script_path = POWERSHELL_SCRIPT.resolve()
        p2vr_template_path = P2VR_TEMPLATE.resolve()

        print(f"DEBUG: Script Path: {script_path}")
        print(f"DEBUG: Processing Path: {source}")
        print(f"DEBUG: Destination Path: {destination}")
        print(f"DEBUG: P2VR Template Path: {p2vr_template_path}")

        if not script_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"PowerShell script '{script_path}' does not exist."
            )

        # Run the PowerShell script
        process = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                str(source),
                str(destination),
                str(p2vr_template_path),
            ],
            capture_output=True,
            text=True,
        )

        # Handle PowerShell script errors
        if process.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"PowerShell script failed with error: {process.stderr}"
            )

        # Return confirmation with the output
        return templates.TemplateResponse(
            "confirmation.html",
            {
                "request": request,
                "status": "success",
                "message": f"Project '{project_name}' processed successfully.",
                "output": process.stdout,
            },
        )
    except Exception as e:
        print(f"Error processing project '{project_name}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing project '{project_name}': {e}",
        )

@app.get("/processed/", response_class=HTMLResponse)
async def view_processed(request: Request):
    """
    List all processed projects and their files in the Processed folder.
    """
    try:
        projects = {}
        for project_dir in PROCESSED_DIR.iterdir():
            if project_dir.is_dir():
                projects[project_dir.name] = [
                    file.name for file in project_dir.glob("**/*") if file.is_file()
                ]

        return templates.TemplateResponse(
            "processed.html",
            {
                "request": request,
                "projects": projects,
            },
        )
    except Exception as e:
        print(f"Error listing processed projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to load processed projects.")
