import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))

from json import loads

from pypenguin.core import *
from pypenguin.opcode_info import info_api, InputMode
from pypenguin.utility import ValidationConfig, grepr

file_path = "../assets/from_online/my 1st platformer.pmp"
#file_path = "../assets/input_modes.pmp"
#file_path = "../assets/monitors.pmp"
#file_path = "../assets/dumb example.pmp"
#file_path = "../assets/testing_blocks.pmp"
#file_path = "../assets/scratch_project.sb3"

project = FRProject.from_file(file_path, info_api=info_api)

#print(project)


new_project = project.step(info_api=info_api)
print(new_project)
new_project.validate(info_api=info_api, config=ValidationConfig())
