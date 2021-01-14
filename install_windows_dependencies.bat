SET PYTHON_MSI=%~dp0python27.msi
msiexec /i %PYTHON_MSI%
C:\Python27\python.exe -m pip install clinical_trials bottle openpyxl xlsxwriter xmltodict requests
pause