import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
import os
import time
time_start = time.time()

print("Hello")

context = bpy.context
data = bpy.data

objects = data.objects
materials = data.materials
images = data.images

def SetupTextures(directory):
    files = os.listdir(directory)
    print("Directory:", directory)
    print("Files in directory:", files)


# This class is a custom directory operator
class ImportTextures(Operator):
    """Import directory information"""
    bl_idname = "import_scene.custom_textures"
    bl_label = "Select Directory"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    
    def invoke(self, context, event):
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        SetupTextures(self.directory)
        return {'FINISHED'}
    
    def run():
        # Register and call
        bpy.utils.register_class(ImportTextures)
        bpy.ops.import_scene.custom_textures('INVOKE_DEFAULT')


def SetupMesh(mesh, path, name="default"):
    # Setup path to files and files themselves
    path_dir = path.rsplit("\\", 1)[0] + "\\"
    files = os.listdir(path_dir)
    
    # Set the object, mesh, and material names
    mesh.name = name
    mesh.data.name = name 
    mtl_name = name + "_mtl"
    active_mtl = mesh.active_material
    
    # If there is no active material, create or append material
    if active_mtl == None:
        try:
            # Check if relevant material exists
            materials[mtl_name]
        except:
            # Material doesnt exists
            newMat = materials.new("newMat")
            mesh.data.materials.append(newMat)
            active_mtl = mesh.active_material
        else:
            # Material does exists
            mesh.data.materials.append(materials[mtl_name])
            active_mtl = mesh.active_material

    active_mtl.name = mtl_name
    active_mtl.use_nodes = True
    active_mtl.displacement_method = "BOTH"

    # Get base node tree and node links
    nodes = active_mtl.node_tree.nodes
    nodes.clear()
    node_links = active_mtl.node_tree.links
    
    # Containers for file types and full names
    file_type = []
    file_full = []
    
    # Filter for type of file - "Albedo, Normal, etc."
    for file in files:
        if file.endswith(".jpg") or file.endswith(".exr"):
            file_full.append(file)
            file = file.rsplit("_", 1)[-1]
            file = file.split(".")[0]
            if not file.find("LOD"): file = "normal"
            file_type.append(file)
    
    # Containers for image node objects and dict for easier access
    image_nodes = []
    image_dictionary = {}
    
    # Creating the image nodes based on textures found
    for x in range(len(file_type)):
        image_node = nodes.new(type="ShaderNodeTexImage")
        image_nodes.append(image_node)
        image_dictionary[file_type[x].lower()] = image_node
        
        image_node.name = file_type[x]
        image_node.location = ((-300 * x), 300)
        image_node.image = images.load(filepath=path_dir+file_full[x], check_existing=True)
        
        # Color management for non-colored images
        if file_type[x] not in ("Albedo", "Displacement", "Specular", "Translucency"):
            image_node.image.colorspace_settings.name = "Non-Color"
        
        # In case of AO map
        if file_type[x].lower() in ("ao"):
            multiply_node = nodes.new(type="ShaderNodeMix")
            multiply_node.data_type = "RGBA"
            multiply_node.blend_type = "MULTIPLY"
            multiply_node.clamp_result = True
            multiply_node.location = (0, -300)
            multiply_node.inputs[0].default_value = 1
    
    # Create rest of nodes
    output_node = nodes.new(type="ShaderNodeOutputMaterial")
    output_node.location = (600, 0)
    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf_node.location = (300, 0)
    disp_node = nodes.new(type="ShaderNodeDisplacement")
    disp_node.location = (-300, -300)
    normal_node = nodes.new(type="ShaderNodeNormalMap")
    normal_node.location = (-600, -300)
    
    # Making connections
    if "ao" in image_dictionary.keys():
        node_links.new(image_dictionary["albedo"].outputs["Color"], multiply_node.inputs["A"])
        node_links.new(image_dictionary["ao"].outputs["Color"], multiply_node.inputs["B"])
        node_links.new(multiply_node.outputs["Result"], bsdf_node.inputs["Base Color"])
    else:
        node_links.new(image_dictionary["albedo"].outputs["Color"], bsdf_node.inputs["Base Color"])
        
    node_links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])
    node_links.new(image_dictionary["normal"].outputs["Color"], normal_node.inputs["Color"])
    node_links.new(normal_node.outputs["Normal"], bsdf_node.inputs["Normal"])
    node_links.new(image_dictionary["specular"].outputs["Color"], bsdf_node.inputs["Specular Tint"])
    node_links.new(image_dictionary["roughness"].outputs["Color"], bsdf_node.inputs["Roughness"])
    node_links.new(image_dictionary["displacement"].outputs["Color"], disp_node.inputs["Height"])
    node_links.new(disp_node.outputs["Displacement"], output_node.inputs["Displacement"])


# This class is a custom file operator
class ImportFbx(Operator, ImportHelper):
    """Import Fbx information"""
    bl_idname = "import_scene.custom_fbx"
    bl_label = "Select Fbx"
    
    def invoke(self, context, event):
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        time_start = time.time()
        previous_objects = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=self.filepath)
        new_objects = set(bpy.context.scene.objects) - previous_objects
        new_objects = list(new_objects)
        
        # Get string name of objects to sort the list 
        sorted_names = [obj.name for obj in new_objects]
        sorted_names.sort()
        
        # Extract a shortened object name from first item
        obj_name = sorted_names[0].rsplit("_", 1)[0]
        obj_name = obj_name.split("Aset_")[-1]
        
        # Group objects if more than one
        if len(new_objects) > 1:
            empty_obj = bpy.ops.object.add(radius=0.1, location=(0.0, 0.0, 0.0))
            empty_obj = context.active_object
            empty_obj.name = obj_name + "_grp"                            
            for obj in new_objects:
                obj.parent = empty_obj
        
        # Setup the materials for objects
        for x in range(len(new_objects)):
            # If first obj setup material, else apply previous mtl
            if x == 0:
                SetupMesh(new_objects[x], self.filepath, obj_name)
            else:
                # Append material to obj, set object and mesh name
                new_objects[x].data.materials.append(materials[obj_name+"_mtl"])
                new_objects[x].name = sorted_names[x].rsplit("_", 1)[0].split("Aset_")[-1]
                new_objects[x].data.name = sorted_names[x].rsplit("_", 1)[0].split("Aset_")[-1]

        print("My Script Finished: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}
    
    @classmethod
    def run(cls):
        # Register and call
        bpy.utils.register_class(ImportFbx)
        bpy.ops.import_scene.custom_fbx('INVOKE_DEFAULT')


ImportFbx.run()
#ImportTextures.run()

#mapping_node = nodes.new(type="ShaderNodeMapping")
#texcoord_node = nodes.new(type="ShaderNodeTexCoord")
#node_dict.update({"MappingNode":mapping_node, "TexCoordNode":texcoord_node})

print("Goodbye")
print("My Script Finished: %.4f sec" % (time.time() - time_start))