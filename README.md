# Python Dependencies Setup for Offline Installation

## Overview

This repository provides a batch script and the necessary requirements files to set up a Python virtual environment, download dependencies for offline installation, and manage Python packages efficiently. It's ideal for scenarios where internet access is limited or unavailable during deployment.

## Contents

- **virtual_setup.bat**: Batch script to automate the creation and management of the Python virtual environment and offline download.
- **jwt_tool-requirements.txt**: Requirements file for the `jwt_tool` script.
- **session_time_analyzer-requirements.txt**: Requirements file for the `session-time-analyzer` script.
- **wheel3/**: Directory containing all downloaded `.whl` files for offline installation.

## Prerequisites

- **Python 3.x** installed on your system.
- **pip** package manager.
- Internet access for the initial download of dependencies.

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/V9Y1nf0S3C/python-offline-dependencies.git
cd python-offline-dependencies
```

### 2. Run the Batch Script

Double-click on `virtual_setup.bat` or run it via the command prompt to execute the setup process.

### 3. Script Breakdown

The `virtual_setup.bat` script performs the following steps:

#### a. Create a Virtual Environment

```bat
python -m venv my_test_env
```

#### b. Activate the Virtual Environment

```bat
my_test_env\Scripts\activate
```

#### c. Check the List of Installed Packages

```bat
pip list
```

#### d. Download Required Packages for Offline Installation

```bat
pip3 download -r https://raw.githubusercontent.com/V9Y1nf0S3C/session-time-analyzer/refs/heads/main/requirements.txt -d .\wheel3\
pip3 download -r https://raw.githubusercontent.com/ticarpi/jwt_tool/refs/heads/master/requirements.txt -d .\wheel3\
```
or
```bat
pip3 download -r jwt_tool-requirements.txt -d .\wheel3\
pip3 download -r session_time_analyzer-requirements.txt -d .\wheel3\
```


#### e. Install All Downloaded `.whl` Files

```bat
for %%x in (.\wheel3\*.whl) do pip install %%x
```

#### f. Verify Installed Packages

```bat
pip list
```

#### g. Deactivate the Virtual Environment

```bat
deactivate
```

#### h. Clean Up (Optional)

The script also includes steps to remove the virtual environment if needed.

## Offline Installation

All downloaded `.whl` files are stored in the `wheel3/` directory. To install these packages on a machine without internet access:

1. Transfer the `wheel3/` directory to the target machine.
2. Activate the virtual environment (optional)
3. Run the installation command:

    ```bash
    for %x in (dir .\wheel3\*.whl) do pip install %x
    ```

## Directory Structure

```
Python-Dependencies/
│
├── jwt_tool-requirements.txt
├── session_time_analyzer-requirements.txt
├── virtual_setup.bat
└── wheel3/
    ├── package1.whl
    ├── package2.whl
    └── ...
```

## Notes

- Ensure that the URLs in the `requirements.txt` files are accessible during the download process.
- The batch script includes pauses to allow the user to proceed step-by-step. You can modify or remove these pauses as needed.
- The `wheel3/` directory is used to store all downloaded wheel files for easy management and offline installation.
