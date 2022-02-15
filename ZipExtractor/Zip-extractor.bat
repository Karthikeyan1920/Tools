@echo off

set input_dir="<input_ZIP_path>"
set output_dir="<Output_directory>"

"<Python_path>" "<Zip-extractor.py_path>" %input_dir% %output_dir%
Pause