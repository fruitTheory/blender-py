import bpy
import os
import sys
import importlib

script_dir = os.path.dirname(bpy.context.space_data.text.filepath)
sys.path.append(script_dir)

from Megascans import ImportMegascans as Mega
importlib.reload(Mega)
Mega.register()

fbx_import = Mega.ImportFbx
#fbx_import.run()

texture_import = Mega.ImportTextures
texture_import.run(Triplanar=False)