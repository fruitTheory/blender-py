import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
import os
import time

print("Hello")

context = bpy.context
data = bpy.data
objects = data.objects
materials = data.materials
images = data.images

def SetupTextures(directory, files, triplanar=False):
    # Get directory name for mtl name
    mtl_name = directory.rsplit("\\", 2)[-2] + "_mtl"
    try:
        # Check if relevant material exists
        materials[mtl_name]
    except:
        # Material doesnt exists
        newMat = materials.new(mtl_name)

    else:
        # Material does exists
        print(f"Material: {mtl_name} already exists.")
        return

    newMat.use_nodes = True
    newMat.displacement_method = "BOTH"

    # Get base node tree and node links
    nodes = newMat.node_tree.nodes
    nodes.clear()
    node_links = newMat.node_tree.links
    
    # Containers for file types and full names
    file_type = []
    file_full = []
    
    # Filter for type of file - "Albedo, Normal, etc."
    for file in files:
        if file.endswith(".jpg") or file.endswith(".exr"):
            file_full.append(file)
            file = file.rsplit("_", 1)[-1]
            file = file.split(".")[0]
            file_type.append(file)
    
    # Cheap check for geo Normal map
    for x in range(len(file_type)):
        if "LOD" in file_type[x]:
            file_type[x] = "Normal"

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
        image_node.image = images.load(filepath=directory+file_full[x], check_existing=True)
        
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
    output_node.location = (900, 0)
    bsdf_node = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf_node.location = (300, 0)

    # Start making connections
    node_links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    # If displacement create and link displacement to disp node and output
    if "displacement" in image_dictionary.keys():
        disp_node = nodes.new(type="ShaderNodeDisplacement")
        disp_node.location = (-300, -300)
        node_links.new(disp_node.outputs["Displacement"], output_node.inputs["Displacement"])
        node_links.new(image_dictionary["displacement"].outputs["Color"], disp_node.inputs["Height"])

    # If ao node then multiply with albedo
    if "ao" in image_dictionary.keys():
        node_links.new(image_dictionary["albedo"].outputs["Color"], multiply_node.inputs["A"])
        node_links.new(image_dictionary["ao"].outputs["Color"], multiply_node.inputs["B"])
        node_links.new(multiply_node.outputs["Result"], bsdf_node.inputs["Base Color"])
    else:
        node_links.new(image_dictionary["albedo"].outputs["Color"], bsdf_node.inputs["Base Color"])
        
    # If normal create and Link normal to normalmap node and to BSDF  
    if "normal" in image_dictionary.keys():
        normal_node = nodes.new(type="ShaderNodeNormalMap")
        normal_node.location = (-600, -300)
        node_links.new(image_dictionary["normal"].outputs["Color"], normal_node.inputs["Color"])
        node_links.new(normal_node.outputs["Normal"], bsdf_node.inputs["Normal"])

    # Check if these common texture nodes exists
    check_link(node_links, image_dictionary, "specular", bsdf_node, "Specular Tint")
    check_link(node_links, image_dictionary, "roughness", bsdf_node, "Roughness")
    check_link(node_links, image_dictionary, "opacity", bsdf_node, "Alpha")

    # If translucency exists create additional BSDF and additional linkage
    if "translucency" in image_dictionary.keys():
        transparent_bsdf = nodes.new(type="ShaderNodeBsdfTransparent")
        transparent_bsdf.location = (0, -600)
        translucent_bsdf = nodes.new(type="ShaderNodeBsdfTranslucent")
        translucent_bsdf.location = (0, -700)
        bsdf_mix_trans = nodes.new(type="ShaderNodeMixShader")
        bsdf_mix_trans.location = (300, -600)
        bsdf_mix_main = nodes.new(type="ShaderNodeMixShader")
        bsdf_mix_main.location = (600, -600)

        node_links.new(image_dictionary["translucency"].outputs["Color"], translucent_bsdf.inputs["Color"])
        check_link(node_links, image_dictionary, "opacity", bsdf_mix_trans, "Fac")
        node_links.new(transparent_bsdf.outputs["BSDF"], bsdf_mix_trans.inputs[1])
        node_links.new(translucent_bsdf.outputs["BSDF"], bsdf_mix_trans.inputs[2])

        node_links.new(bsdf_node.outputs["BSDF"], bsdf_mix_main.inputs[1])
        node_links.new(bsdf_mix_trans.outputs["Shader"], bsdf_mix_main.inputs[2])
        node_links.new(bsdf_mix_main.outputs["Shader"], output_node.inputs["Surface"])

    # If triplanar setup object mapping with box projection, else setup with UV and no projections
    if triplanar:
        texcoord_node = nodes.new(type="ShaderNodeTexCoord")
        texcoord_node.location = (-1800, -200)
        mapping_node = nodes.new(type="ShaderNodeMapping")
        mapping_node.location = (-1600, -200)
        value_node = nodes.new(type="ShaderNodeValue")
        value_node.outputs[0].default_value = 1.0
        value_node.location = (-1900, -600)
        node_links.new(value_node.outputs["Value"], mapping_node.inputs["Scale"])
        node_links.new(texcoord_node.outputs["Object"], mapping_node.inputs["Vector"])
        for node in image_nodes:
            node_links.new(mapping_node.outputs["Vector"], node.inputs["Vector"])
            node.projection = "BOX"
    else:
        texcoord_node = nodes.new(type="ShaderNodeTexCoord")
        texcoord_node.location = (-1800, -200)
        mapping_node = nodes.new(type="ShaderNodeMapping")
        mapping_node.location = (-1600, -200)
        value_node = nodes.new(type="ShaderNodeValue")
        value_node.outputs[0].default_value = 1.0
        value_node.location = (-1900, -600)
        node_links.new(value_node.outputs["Value"], mapping_node.inputs["Scale"])
        node_links.new(texcoord_node.outputs["UV"], mapping_node.inputs["Vector"])
        for node in image_nodes:
            node_links.new(mapping_node.outputs["Vector"], node.inputs["Vector"])



# Check if link can be made, needs nodelink obect, output node, name, input node, and input type
def check_link(node_links, node_out, node_name, node_in, in_type):
    try:
        node_links.new(node_out[node_name].outputs["Color"], node_in.inputs[in_type])
    except:
        pass


# Class to import directory containing textures
class ImportTextures(Operator):
    """Import texture information"""
    bl_idname = "import_scene.custom_textures"
    bl_label = "Select Directory"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    triplanar: bpy.props.BoolProperty(name="Triplanar", description="Use Triplanar?")
    
    def invoke(self, context, event):
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        time_start = time.time()
        files = os.listdir(self.directory)
        SetupTextures(self.directory, files, self.triplanar)

        mtl_name = self.directory.rsplit("\\", 2)[-2] + "_mtl"
        # Optional design, assign material to active object
        active_obj = bpy.context.active_object
        try:
            active_obj.data.materials.pop(index=0)
        except:
            print("Warning: Material slot empty.")
        active_obj.data.materials.append(bpy.data.materials[mtl_name])

        print("My Script Finished: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}
    
    @classmethod
    def run(cls, Triplanar=False):
        bpy.ops.import_scene.custom_textures('INVOKE_DEFAULT', triplanar=Triplanar)


# Class to import plant and variant directories
class ImportVariants(Operator):
    """Import variant information"""
    bl_idname = "import_scene.custom_variants"
    bl_label = "Select Directory"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    
    def invoke(self, context, event):
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        time_start = time.time()

        # Get variant folders and append to list
        folders = os.listdir(self.directory)
        var_folders = []
        for folder in folders:
            if folder.find("Var") != -1:
                var_folders.append(folder)

        # Get the difference of objects to get new objects, import objects
        previous_objects = set(bpy.context.scene.objects)
        for folder in var_folders:
            bpy.ops.import_scene.fbx(filepath=self.directory+folder+"\\"+(folder+"_LOD0.fbx"))

        new_objects = set(bpy.context.scene.objects) - previous_objects
        new_objects = list(new_objects)

        # Remove default material, then remove the slot
        for object in new_objects:
            bpy.data.materials.remove(object.active_material)
            object.data.materials.pop(index=0)

        # Get texture files, store file directory, and parent directory name
        files = os.listdir(self.directory + "//textures//atlas//")
        file_directory = self.directory + "//textures//atlas//"
        parent_name = self.directory.rsplit("\\", 2)[-2]

        # Create a collection if relevant one doesnt exist, else use existing
        try: 
            bpy.data.collections[parent_name]
        except:
            collection = bpy.data.collections.new(name=parent_name)
        else:
            collection = bpy.data.collections[parent_name]
        
        # Get active LayerCollection and from that the core Collection
        active_layer_collection = bpy.context.view_layer.active_layer_collection
        default_collection = active_layer_collection.collection

        # Unlink from default collection and link with relevant one
        for object in new_objects:
            default_collection.objects.unlink(object)
            collection.objects.link(object) 

        try:
            # Link collection children to scene context
            bpy.context.scene.collection.children.link(collection)
        except:
            print("Already in collection")

        SetupTextures(file_directory, files)

        # Try assigning materials
        try:
            for object in new_objects:
                object.data.materials.append(materials[parent_name + "_mtl"])
        except:
            print(f"Material {parent_name}_mtl is not found.")

        print("My Script Finished: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}
    
    @classmethod
    def run(cls):
        bpy.ops.import_scene.custom_variants('INVOKE_DEFAULT')


# Class to import fbx with directory containing textures
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

        # Get any newly imported objects
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
        
        # Store directory path, files, and mtl name
        directory = self.filepath.rsplit("\\", 1)[0] + "\\"
        files = os.listdir(directory)
        mtl_name = directory.rsplit("\\", 2)[-2] + "_mtl"
  
        SetupTextures(directory, files)

        # Check the active collection and if not default then unlink and relink
        active_layer_collection = bpy.context.view_layer.active_layer_collection
        active_collection = active_layer_collection.collection
        scene_collection = bpy.context.scene.collection
        for object in new_objects:
            if scene_collection != active_collection:
                active_collection.objects.unlink(object)
                scene_collection.objects.link(object)

        # Try assigning materials
        try:
            for object in new_objects:
                try:
                    # Pop default mtl before appending mtl
                    object.data.materials.pop(index=0)
                except:
                    continue
                object.data.materials.append(materials[mtl_name])
        except:
            print(f"Material {mtl_name} is not found.")

        print("My Script Finished: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}
    
    @classmethod
    def run(cls):
        bpy.ops.import_scene.custom_fbx('INVOKE_DEFAULT')


def register():
    bpy.utils.register_class(ImportFbx)
    bpy.utils.register_class(ImportTextures)
    bpy.utils.register_class(ImportVariants)

def unregister():
    bpy.utils.unregister_class(ImportFbx)
    bpy.utils.register_class(ImportTextures)
    bpy.utils.register_class(ImportVariants)

# Avoid execution on import
if __name__ == "__main__":
    register()


print("Goodbye")