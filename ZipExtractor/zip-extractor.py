import os
from zipfile import ZipFile
import sys
import shutil

if len(sys.argv) == 3:
    # Get the arguments from batch file
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

# Replicate the original zip file to target directory
target = output_dir + "\\" + os.path.basename(input_dir)
shutil.copyfile(input_dir, target)

# Give the input directory in listOffiles
extension = ".zip"
listOfiles = [target]
dir_name_base = os.path.dirname(listOfiles[0])
with ZipFile(listOfiles[0], 'r') as zipObj:
    # Get list of files names in zip
    files = zipObj.namelist()
for file in files:
    if ".zip" in file:
        listOfiles.append(file)
current = 1
# Count the number of zips

for file in listOfiles:
    print("Extracting  files: ", current, "/", len(listOfiles))
    current += 1
    dir_name = os.path.dirname(file)
    if dir_name != dir_name_base:
        dir_name = dir_name_base + "\\" + dir_name.replace("/", "\\")
    os.chdir(dir_name)
    # Change the directory from working to current
    for item in os.listdir(dir_name):
        # Loop through teh files in directory
        if item.endswith(extension):
            # Check for ".zip" extension
            file_name = os.path.abspath(item)
            # Get full path of files
            zip_ref = ZipFile(file_name)
            # Create a zipfile object
            zip_ref.extractall(dir_name)
            # Extract file to Directory
            # Delete all the zip files
            zip_ref.close()
            # close file
            os.remove(file_name)
            # Delete zipped file
print("File is ready to use")
