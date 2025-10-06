#python -m pip debug --verbose

import os
import sys
import subprocess
import logging
import argparse
import shlex  # Used for safer command display in logs
import re
import shutil
import time
import statistics # Needed for average calculation

# --- Configuration ---
DEFAULT_REQ_FILE = 'requirements.txt'
DEFAULT_DOWNLOAD_DIR = 'wheels_offline'

# --- Global list to store execution times ---
pip_call_times = []


# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

# --- Helper Function to Run Pip (Handles Dependencies) ---
def run_pip_download_deps(package_spec, original_package_name, download_dir, attempt_desc, extra_args=None):
    """
    Runs 'pip download' resolving dependencies.

    Args:
        package_spec (str): The package requirement string(s) to pass to pip (can be modified).
        original_package_name (str): The original package name used for directory creation.
        download_dir (str): The BASE directory to download wheels into.
        attempt_desc (str): Description of the attempt (e.g., '[1/12] Pkg: requests - Attempt [1/80]').
        extra_args (list, optional): Additional arguments like platform/version flags.

    Returns:
        bool: True if pip command exited with code 0, False otherwise.
    """
    global pip_call_times # Declare we are using the global variable
    start_time_pip = time.perf_counter() # Start timing the call

    if extra_args is None:
        extra_args = []


    # Sanitize the ORIGINAL package name for the directory
    sanitized_package_name = re.sub(r'[^a-zA-Z0-9_-]', '', original_package_name)
    # Create the specific subdirectory path using the sanitized ORIGINAL name
    package_subdir = os.path.join(download_dir, sanitized_package_name)

    # Ensure the subdirectory exists
    try:
        os.makedirs(package_subdir, exist_ok=True)
        logging.debug(f"    Ensured subdirectory exists: {package_subdir}")
    except OSError as e:
        logging.error(f"    Failed to create subdirectory {package_subdir}: {e}")
        # Decide if this is fatal or if pip download might still work if dir exists
        return False # Return failure here as download dest is compromised

    # Base arguments - download into the specific package subdirectory
    base_command = [
        'pip', 'download',
        '--dest', package_subdir,
        '--disable-pip-version-check',
    ]
    # Use the potentially modified package_spec for the pip command
    package_spec_list = package_spec.split()
    command = base_command + (extra_args if extra_args else []) + package_spec_list
    logging.debug(f"    Full command ({attempt_desc}): {' '.join(shlex.quote(arg) for arg in command)}") # Added attempt desc to debug

    success = False
    try:
        # Consider adding a timeout to subprocess.run if needed
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore') #, timeout=300) # Example 5-min timeout

        if result.returncode == 0:
            logging.debug(f"    Pip exited cleanly for {attempt_desc} (Spec: {package_spec}).")
            success = True
        else:
            # Log failures clearly - include the attempt description
            log_prefix = f"    Pip command failed for {attempt_desc} (Spec: {package_spec})" # <<< MODIFIED: Included attempt_desc
            log_suffix = f"(Return Code: {result.returncode})."
            stderr_msg = result.stderr.strip().replace('\n', ' ') if result.stderr else "(No stderr output)"
            stdout_msg = f"\n    Pip stdout (on error):\n{result.stdout.strip()}" if result.stdout and result.returncode != 0 else ""
            # Use warning level for failures
            logging.warning(f"{log_prefix} {log_suffix} Stderr: {stderr_msg}{stdout_msg}")
            success = False
    except FileNotFoundError:
        logging.error(f"    ERROR: Cannot find 'pip'. Is Python installed correctly and in PATH? ({attempt_desc})")
        success = False
    #except subprocess.TimeoutExpired:
    #    logging.error(f"    ERROR: Pip command timed out for {attempt_desc} (Spec: {package_spec})")
    #    success = False
    except Exception as e:
        logging.error(f"    ERROR: An unexpected error occurred during pip execution for {attempt_desc} (Spec: {package_spec}): {e}")
        success = False
    finally:
        end_time_pip = time.perf_counter() # End timing the call
        elapsed_pip = end_time_pip - start_time_pip
        pip_call_times.append(elapsed_pip) # Store the duration
        logging.debug(f"    Pip call duration for {attempt_desc}: {elapsed_pip:.4f} seconds")

    return success


# --- Function to Download Package + Deps with Multiple Strategies ---
def download_package_with_deps(package_spec, download_dir, package_progress_str):
    """
    Downloads a package and its dependencies using multiple strategies for offline use.

    Args:
        package_spec (str): The original package requirement string from requirements.txt.
        download_dir (str): The BASE download destination directory.
        package_progress_str(str): String indicating overall package progress (e.g., "[1/10]").

    Returns:
        bool: True if at least one download attempt was successful, False otherwise.
    """
    # Extract only the original package name part for logging, dir name, and potential lookup
    original_package_name_only = re.split(r'[<>=!~]', package_spec)[0].strip()
    logging.info(f"Processing {package_progress_str}: [{original_package_name_only}] (Full spec: {package_spec})")
    download_success = False # Tracks if ANY attempt succeeded for this package

    attempt = 0
    attempt_success_count = 0 # Tracks successful attempts for THIS package

    # --- Define Download Strategies ---
    TARGET_PLATFORM_ALT = 'win_amd64' # Example platform
    var_platforms = ['any', TARGET_PLATFORM_ALT]

    var_python_versions=['3.13','3.12','3.11','3','3.14','3.15','3.16'] # Target Python versions

    var_implementations = ['cp', 'py']
    var_binary_types = ['--only-binary=:all:'] # Force binary downloads

    DOWNLOAD_ALL_VERSIONS = True  # Set to True to try all strategies even after first success
    COPY_FIRST_SET_TO_PARENT_DIRECTORY = False # Set True to copy wheels from first successful attempt's subdir to base dir

    download_strategies = []
    # Build strategy list dynamically
    for var_platform in var_platforms:
        for var_python_version in var_python_versions:
            # <<< MODIFIED: Generate specific_abis dynamically >>>
            if '.' in var_python_version:
                # Format like cp313, cp312 etc.
                abi_specific = f"cp{var_python_version.replace('.', '')}"
            elif len(var_python_version) == 1:
                # Format like abi3, abi4 etc. for major versions
                abi_specific = f"abi{var_python_version}"
            else:
                 # Fallback or handle other formats if needed
                 abi_specific = f"cp{var_python_version}" # Assuming cpXY if no dot and not single digit

            specific_abis = ['none', abi_specific]
            # --- End dynamic ABI generation ---

            for var_abi in specific_abis:
                for var_implementation in var_implementations:
                    # Skip invalid combinations (e.g., py implementation with CPython abi)
                    if var_implementation == 'py' and var_abi.startswith(('cp', 'abi')):
                         continue
                    # Skip 'none' abi for 'cp' implementation? Maybe not necessary, pip might handle it.
                    # if var_implementation == 'cp' and var_abi == 'none':
                    #     continue

                    for var_binary_type in var_binary_types:
                        strategy = ['--platform', var_platform, '--python-version', var_python_version, '--abi', var_abi, '--implementation', var_implementation, var_binary_type]
                        download_strategies.append(strategy)

    # Add the default/current environment strategy (empty list signifies current env)
    download_strategies.append([])
    total_attempts = len(download_strategies)


    #download_strategies = [
    #    ['--platform', 'any', '--abi', 'none', '--implementation', 'cp', '--python-version', TARGET_PYTHON_ALT, '--only-binary', ':all:'],
    #    ['--platform', 'any', '--abi', 'abi3', '--implementation', 'cp', '--python-version', TARGET_PYTHON_MAJOR_AGNOSTIC, '--only-binary', ':all:'],
    #    ['--platform', 'any', '--abi', 'none', '--implementation', 'py', '--python-version', TARGET_PYTHON_MAJOR_AGNOSTIC, '--only-binary', ':all:'],
    #    ['--platform', 'any', '--abi', 'cp313', '--implementation', 'py', '--python-version', TARGET_PYTHON_MAJOR_AGNOSTIC, '--only-binary', ':all:'],
    #    ['--platform', TARGET_PLATFORM_ALT, '--abi', TARGET_PYTHON, '--implementation', 'py', '--python-version', TARGET_PYTHON_MAJOR_AGNOSTIC, '--only-binary', ':all:'],
    #    ['--platform', TARGET_PLATFORM_ALT, '--abi', TARGET_PYTHON, '--implementation', 'cp', '--only-binary', ':all:'],
    #    [],
    #    ['--platform', 'any', '--abi', 'none', '--implementation', 'py', '--python-version', TARGET_PYTHON_MAJOR_AGNOSTIC, '--only-binary', ':all:'],
    #    ['--python-version', TARGET_PYTHON_ALT, '--platform', TARGET_PLATFORM_ALT, '--implementation', 'cp']
    #]

    # --- Loop through download strategies ---
    for strategy in download_strategies:
        # Decide whether to continue attempting
        if not download_success or DOWNLOAD_ALL_VERSIONS:
            attempt += 1
            attempt_progress_str = f"[{attempt}/{total_attempts}]" # Attempt progress string
            strategy_desc = ' '.join(map(str, strategy)) if strategy else "Current Env / Default"
            # <<< MODIFIED: Include package_progress_str in attempt log >>>
            logging.info(f"  {package_progress_str} Attempt {attempt_progress_str}: Strategy = {strategy_desc}")

            # Handle known dependencies explicitly if needed
            known_dependencies = {'pyautogui': 'pyautogui setuptools wheel'}
            spec_for_pip = known_dependencies.get(original_package_name_only.lower(), package_spec)

            # <<< MODIFIED: Include package_progress_str in attempt_desc passed to run_pip >>>
            detailed_attempt_desc = f"{package_progress_str} Pkg: {original_package_name_only} - Attempt {attempt_progress_str}"

            # Run pip download
            success = run_pip_download_deps(
                package_spec=spec_for_pip,
                original_package_name=original_package_name_only,
                download_dir=download_dir,
                attempt_desc=detailed_attempt_desc, # Pass detailed description
                extra_args=strategy
            )

            if success:
                attempt_success_count += 1
                # <<< MODIFIED: Include package_progress_str in success log >>>
                logging.info(f"    {package_progress_str} Attempt {attempt_progress_str} SUCCEEDED for spec '{spec_for_pip}' with strategy: {strategy_desc}")
                download_success = True # Mark that at least one attempt worked

                # Actions on FIRST successful download for this package
                if attempt_success_count == 1:
                    sanitized_original_package_name = re.sub(r'[^a-zA-Z0-9_-]', '', original_package_name_only)
                    package_subdir_path = os.path.join(download_dir, sanitized_original_package_name)

                    # Write to installation batch file
                    try:
                        with open("installation-instructions.bat", "a") as f:
                            f.write(f"REM Install '{package_spec}' (Original requirement)\n")
                            f.write(f'pip install --no-index --find-links ".\\{package_subdir_path}" "{package_spec}"\n\n')
                    except IOError as e:
                         logging.error(f"    Failed to write install instruction for {package_spec}: {e}")


                    # Copy files if requested
                    if COPY_FIRST_SET_TO_PARENT_DIRECTORY:
                        src_dir = package_subdir_path
                        dst_dir = download_dir
                        logging.info(f"    {package_progress_str} Copying wheels from first successful attempt ({src_dir}) to base ({dst_dir})...") # Added progress
                        try:
                            if os.path.isdir(src_dir):
                                for item_name in os.listdir(src_dir):
                                    src_item = os.path.join(src_dir, item_name)
                                    dst_item = os.path.join(dst_dir, item_name)
                                    if os.path.isfile(src_item):
                                        logging.debug(f"      Copying {src_item} to {dst_item}")
                                        shutil.copy2(src_item, dst_item)
                            else:
                                logging.warning(f"    {package_progress_str} Source directory for copying not found or not a directory: {src_dir}") # Added progress
                        except Exception as copy_err:
                            logging.error(f"    {package_progress_str} Error copying files from {src_dir} to {dst_dir}: {copy_err}") # Added progress

                # If not downloading all versions, break after the first success
                if not DOWNLOAD_ALL_VERSIONS:
                    logging.info(f"  {package_progress_str} First successful download achieved for {original_package_name_only}. Stopping attempts.") # Added progress
                    break
            else:
                 # <<< MODIFIED: Include package_progress_str in failure log >>>
                 logging.warning(f"    {package_progress_str} Attempt {attempt_progress_str} FAILED for spec '{spec_for_pip}' with strategy: {strategy_desc}")


     # Log final status for the package
    if download_success:
         logging.info(f"Successfully downloaded artifacts for {package_progress_str} [{original_package_name_only}] in {attempt_success_count} attempt(s).") # Added progress
    else:
         logging.error(f"FAILED to download any suitable artifacts for {package_progress_str} [{original_package_name_only}] after {total_attempts} attempts.") # Added progress

    return download_success


# --- Main Execution Logic ---
def main():
    global pip_call_times # Access the global list
    pip_call_times = [] # Ensure it's empty at the start

    start_time = time.perf_counter() # Record start time

    parser = argparse.ArgumentParser(
        description='Download Python wheels and their dependencies from a requirements file for offline installation.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', '--requirements', default=DEFAULT_REQ_FILE, help='Path to the requirements file.')
    parser.add_argument('-d', '--dest', default=DEFAULT_DOWNLOAD_DIR, help='Directory to download wheels into.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug logging.')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled.")

    requirements_file = args.requirements
    download_dir = args.dest
    processed_count = 0
    successful_packages = []
    failed_packages = []

    # --- Pre-run Checks ---
    if not os.path.isfile(requirements_file):
        logging.error(f"Requirements file not found: {requirements_file}")
        sys.exit(1)
    try:
        # Create the BASE download directory first
        os.makedirs(download_dir, exist_ok=True)
        logging.info(f"Using base download directory: {os.path.abspath(download_dir)}")
    except OSError as e:
        logging.error(f"Failed to create base directory {download_dir}: {e}")
        sys.exit(1)

    # --- Read Requirements and Count Valid Packages ---
    valid_package_lines = []
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                package_spec = line.strip()
                # Apply the same filtering logic used in the processing loop
                if not package_spec or package_spec.startswith('#'): continue
                if ' #' in package_spec: package_spec = package_spec.split(' #', 1)[0].strip()
                if not package_spec: continue
                if package_spec.startswith(('-', '--')): continue # Skip options
                valid_package_lines.append(package_spec)
    except IOError as e:
        logging.error(f"Failed to read requirements file {requirements_file}: {e}")
        sys.exit(1)

    total_packages_to_process = len(valid_package_lines)
    if total_packages_to_process == 0:
        logging.warning(f"No valid package specifications found in {requirements_file}.")
        # Exit early or continue to summary depending on desired behavior
        # sys.exit(0)

    logging.info(f"Found {total_packages_to_process} packages to process in '{requirements_file}'.")
    logging.info(f"Starting offline dependency download...")
    logging.info("==================================================================")

    # --- Setup installation batch file ---
    try:
        with open("installation-instructions.bat", "w") as f:
            f.write(f"@echo off\n")
            f.write(f"REM Auto-generated batch file for offline installation\n")
            f.write(f"REM Base wheel directory: {os.path.abspath(download_dir)}\n")
            f.write(f"echo.\n")
            f.write(f"REM --- Optional: Create and activate a virtual environment --- \n")
            f.write(f"REM python -m venv my_offline_env\n")
            f.write(f"REM call my_offline_env\\Scripts\\activate\n")
            f.write(f"echo.\n")
            f.write(f"echo Checking pip version and compatible tags...\n")
            f.write(f"pip --version\n")
            f.write(f"pip debug --verbose\n")
            f.write(f"echo.\n")
            f.write(f"echo Listing packages before installation...\n")
            f.write(f"pip list\n")
            f.write(f"echo ============================================================\n")
            f.write(f"echo Starting installations...\n")
            f.write(f"echo.\n")
    except IOError as e:
        logging.error(f"Failed to write initial installation-instructions.bat: {e}")
        # Decide if this is critical

    # --- Process Each Valid Package ---
    for package_spec in valid_package_lines:
        processed_count += 1
        package_progress_str = f"[{processed_count}/{total_packages_to_process}]" # Package progress string

        # Call the function to download the package and its dependencies
        # Pass the original package_spec from the requirements file
        if download_package_with_deps(package_spec, download_dir, package_progress_str):
            successful_packages.append(package_spec)
        else:
            failed_packages.append(package_spec)
        logging.info("------------------------------------------------------------------") # Separator between packages

    # --- Finalize installation batch file ---
    try:
        with open("installation-instructions.bat", "a") as f:
            f.write(f"echo.\n")
            f.write(f"echo ============================================================\n")
            f.write(f"echo Installation commands executed.\n")
            f.write(f"echo Listing packages after installation...\n")
            f.write(f"pip list\n")
            f.write(f"echo ============================================================\n")
            f.write(f"REM --- Optional: Deactivate virtual environment ---\n")
            f.write(f"REM call deactivate\n")
            f.write(f"echo.\n")
            f.write(f"echo Script finished. Closing in 500 seconds...\n")
            f.write(f"timeout /t 500 /nobreak > nul\n")
    except IOError as e:
         logging.error(f"Failed to finalize installation-instructions.bat: {e}")


    # --- Final Summary ---
    logging.info("==================================================================")
    logging.info("Offline dependency download process finished.")
    logging.info(f"Processed {processed_count}/{total_packages_to_process} top-level requirements from '{requirements_file}'.")
    logging.info(f"{len(successful_packages)} packages had at least one successful download strategy.")

    if failed_packages:
        logging.warning(f"FAILED to download any suitable artifacts for {len(failed_packages)} packages after all attempts:")
        for pkg in failed_packages:
            logging.warning(f"  - {pkg}")
        logging.warning("Offline installation will likely fail for these packages.")

    logging.info(f"Downloaded wheels are organized in subdirectories within: {os.path.abspath(download_dir)}")
    logging.info(f"Review 'installation-instructions.bat' for offline installation steps.")

    # --- Timing Statistics ---
    if pip_call_times:
        min_time = min(pip_call_times)
        max_time = max(pip_call_times)
        # Calculate average only if there are times, handle potential empty list if script fails early
        avg_time = statistics.mean(pip_call_times) if pip_call_times else 0
        total_time_pip = sum(pip_call_times)
        logging.info("--- Pip Download Timing Statistics ---")
        logging.info(f"  Total pip download calls: {len(pip_call_times)}")
        logging.info(f"  Total time in pip calls: {total_time_pip:.2f} seconds")
        logging.info(f"  Minimum time per call:   {min_time:.4f} seconds")
        logging.info(f"  Maximum time per call:   {max_time:.4f} seconds")
        logging.info(f"  Average time per call:   {avg_time:.4f} seconds")
    else:
        logging.info("--- No pip download calls were recorded. ---")


    end_time = time.perf_counter() # Record end time
    elapsed_seconds = end_time - start_time # Calculate duration in seconds

    # Convert to minutes and remaining seconds
    minutes = int(elapsed_seconds // 60)
    seconds = elapsed_seconds % 60

    # Print the formatted time
    logging.info(f"\n--- Script finished in: {minutes} minutes and {seconds:.2f} seconds ---")

if __name__ == "__main__":
    main()