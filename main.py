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

# Note: Issue with pop() if slots empty, also may not be good to totally delete existing material
texture_import = Mega.ImportTextures
texture_import.run(Triplanar=True)

#variant_import = Mega.ImportVariants
variant_import.run()