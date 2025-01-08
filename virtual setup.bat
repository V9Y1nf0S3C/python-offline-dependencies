@echo off
echo =============================================================================
echo   Batch Script to downlaod and test python packages for offline installation
echo =============================================================================

echo.
echo 1.Press any key to create a Python virtual environment 'my_test_env'
echo.
pause >nul
echo   creating virtual environment...

REM Create a virtual environment named my_test_env
python -m venv my_test_env

echo.
echo 2.Virtual environment created. Press any key to activate
echo.
pause >nul

REM Activate the virtual environment
call my_test_env\Scripts\activate

REM List installed packages in the virtual environment
echo   Here are the lsit of pckages available on virtual environment...
pip list

echo.
echo 3.Press any key to download required packages for offline installation
echo.
pause >nul


REM Download dependencies from the first requirements.txt to the wheel3 directory
pip3 download -r https://raw.githubusercontent.com/V9Y1nf0S3C/session-time-analyzer/refs/heads/main/requirements.txt -d .\wheel3\

REM Download dependencies from the second requirements.txt to the wheel3 directory
pip3 download -r https://raw.githubusercontent.com/ticarpi/jwt_tool/refs/heads/master/requirements.txt -d .\wheel3\

echo.
echo 4.Press any key to install the downloaded packages (offline installation test)
echo.
pause >nul

REM Install all wheel files from the wheel3 directory
for %%x in (.\wheel3\*.whl) do (
    pip install %%x
)

REM List installed packages after installation
echo   Here are the lsit of pckages available now on virtual environment...
pip list

echo.
echo 5.Press any key to deactivate the virtual environment and exit
echo.
pause >nul

REM Deactivate the virtual environment
call deactivate

echo.
echo 6.Press any key to remove the test environment 'my_test_env'
echo.
pause >nul

REM Remove the virtual environment directory
rmdir /S /Q my_test_env

echo.
echo All steps completed. You can use the offline packages in the path: .\wheel3
echo.
echo Here is the list of available packages:
dir .\wheel3

echo.
echo 
echo =============================================================================
echo                    Task completed. Going to exit
echo =============================================================================
pause >nul
pause >nul
pause >nul
exit /b
