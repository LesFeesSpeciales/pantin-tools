# Copyright (C) 2017 Les Fees Speciales
# voeu@les-fees-speciales.coop
#
# Created by Les Fees Speciales
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Parent planes to bones",
    "author": "Les Fees Speciales",
    "version": (1, 0),
    "blender": (2, 77, 0),
    "location": "View3D > Tool > Parent planes to bones",
    "description": """In-house tool to
                      * generate UUIDS for pantins at rig phase, used by other tools
                      * automatically parent planes to bones based on names
                      * add animatable plane variations
                      """,
    "warning": "",
    "wiki_url": "",
    "category": "LFS",
    }

import bpy
import re
from bpy.types import Operator
from rna_prop_ui import rna_idprop_ui_prop_get
from uuid import uuid4
from bpy.props import StringProperty

def strip_numbers(name):
    """ Returns the name with trailing numbers stripped from it.
    """
    # regexp = re.compile("\.[0-9]+$")
    matches = re.findall("\.[0-9]+$", name)
    if matches:
        return name[:-len(matches[-1])]
    else:
        return name

SUFFIX_HIERARCHY = {
    ".L": "_gauche",
    ".R": "_droit"
}

def do_parenting(arm, bone, plane, grp, plane_meshes=None):
    mat = plane.matrix_world.copy()

    plane.parent = arm
    plane.parent_type = 'BONE'
    plane.parent_bone = bone.name
    plane.matrix_world = mat
    plane.hide_select = True
    plane.name = strip_numbers(plane.name)

    # Fix for shear matrix: set the plane's space to the parent bone's
    parent_pbone = arm.pose.bones[bone.name]
    # print(parent_pbone)
    if plane_meshes is None or not plane.data in plane_meshes: # mesh has not yet been processed
        for v in plane.data.vertices:
            v.co = (arm.matrix_world * parent_pbone.matrix).inverted() * mat * v.co
        if plane_meshes is not None:
            plane_meshes.append(plane.data)
    # else:
    #     print(plane.name)
    plane.matrix_world = arm.matrix_world * parent_pbone.matrix

    # Assign uuid to plane object
    if not "db_uuid" in plane:
        plane["db_uuid"] = str(uuid4())
    # Add plane to group
    if not plane.name in grp.objects:
        grp.objects.link(plane)

    return plane_meshes

def parent_planes_to_bones(self, context):
    arm = context.object
    initial_position = arm.data.pose_position
    arm.data.pose_position = 'REST'
    context.scene.update()

    # Assign uuid to armature object
    if not "db_uuid" in arm:
        arm["db_uuid"] = str(uuid4())

    # Group
    if not arm.name in bpy.data.groups:
        grp = bpy.data.groups.new(arm.name)
    else:
        grp = bpy.data.groups[arm.name]

    if not "db_uuid" in grp:
        grp["db_uuid"] = str(uuid4())

    if not arm.name in grp.objects:
        grp.objects.link(arm)

    plane_meshes = []
    for b in arm.data.bones:
        if b.use_deform:
            bone_name = b.name
            if bone_name[:4] == 'DEF-':
                bone_name = bone_name[4:]
            if bone_name[-2:] in ['.L', '.R']:
                obj_name, suffix = bone_name[:-2].replace(' ', '_'), bone_name[-2:]
                # Check for object existing
                if obj_name + suffix in bpy.data.objects:
                    obj_name += suffix
                    new_name = obj_name
                elif obj_name + SUFFIX_HIERARCHY[suffix] in bpy.data.objects:
                    new_name = obj_name + suffix
                    obj_name += SUFFIX_HIERARCHY[suffix]
                elif obj_name + suffix.replace('.', '_') in bpy.data.objects:
                    new_name = obj_name + suffix.replace('.', '_')
                    obj_name = new_name
                elif obj_name in bpy.data.objects:
                    new_name = obj_name + suffix
                else:
                    self.report({"WARNING"}, "Could not find object %s (%s)" % (obj_name, suffix))
                    continue

                p = bpy.data.objects[obj_name]

                # Check that object is not already parented
                if bone_name.replace(' ', '_') in context.scene.objects and (context.scene.objects[bone_name.replace(' ', '_')].parent == arm and context.scene.objects[bone_name.replace(' ', '_')].parent_bone == b.name):
                    self.report({"WARNING"}, "Object %s already child of bone %s" % (obj_name, b.name))
                    continue
                if new_name in bpy.context.scene.objects:
                    p = bpy.data.objects[new_name]
                    # bpy.context.scene.objects.unlink(bpy.data.objects[new_name])
                elif obj_name in bpy.data.objects:
                    do_reapply_mat = False
                    grps = p.users_group
                    for g in grps:
                        g.objects.unlink(p)
                    if obj_name in bpy.context.scene.objects:
                        do_reapply_mat = True
                        mat = p.matrix_world.copy()
                        bpy.context.scene.objects.unlink(bpy.data.objects[obj_name])
                        bpy.data.objects[obj_name].user_clear()
                    p = bpy.data.objects.new(new_name, p.data)
                    bpy.context.scene.objects.link(p)
                    for g in grps:
                        g.objects.link(p)
                    if do_reapply_mat:
                        p.matrix_world = mat


                # elif obj_name in bpy.context.scene.objects: # copy original object
                #     mat = p.matrix_world.copy()
                #     bpy.context.scene.objects.unlink(bpy.data.objects[obj_name])
                #     bpy.data.objects[obj_name].user_clear()
                #     p = bpy.data.objects.new(new_name, p.data)
                #     bpy.context.scene.objects.link(p)
                #     p.matrix_world = mat
                # elif obj_name in bpy.data.objects: # copy original object
                #     # mat = p.matrix_world.copy()
                #     # bpy.context.scene.objects.unlink(bpy.data.objects[obj_name])
                #     # bpy.data.objects[obj_name].user_clear()
                #     p = bpy.data.objects.new(new_name, p.data)
                #     bpy.context.scene.objects.link(p)
                #     # p.matrix_world = mat
                #     print(obj_name)
            else:
                if not bone_name.replace(' ', '_') in bpy.data.objects:
                    self.report({"WARNING"}, "Could not find object %s" % bone_name)
                    continue
                p = bpy.data.objects[bone_name.replace(' ', '_')]

            plane_meshes = do_parenting(arm, b, p, grp, plane_meshes)

#                print("Could not connect", s.name)
    arm.data.pose_position = initial_position

    # uuid in texts
    for txt in bpy.data.texts:
        if txt.name.startswith('rig_ui') and not "db_uuid" in txt:
            txt["db_uuid"] = str(uuid4())


def unparent_planes_from_bones(self, context):
    arm = context.object
    initial_position = arm.data.pose_position
    arm.data.pose_position = 'REST'
    context.scene.update()

    for child in arm.children:
        if child.type == 'MESH':
            mat = child.matrix_world.copy()
            child.parent = None
            child.matrix_world = mat
            child.hide_select = False

    arm.data.pose_position = initial_position


class OBJECT_OT_parent_planes_to_bones(Operator):
    """Parent planes to bones"""
    bl_idname = "lfs.parent_planes_to_bones"
    bl_label = "Parent planes to bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        parent_planes_to_bones(self, context)

        return {'FINISHED'}


def remove_variation(obj, name):
    if obj and obj.type == 'ARMATURE':
        prop_name = "variation_{}".format(name)
        del bpy.context.object['{}'.format(prop_name)]


class OBJECT_OT_delete_variation(Operator):
    """Delete variation property"""
    bl_idname = "lfs.delete_variation"
    bl_label = "Delete_variation"
    bl_options = {'REGISTER', 'UNDO'}

    var_name = StringProperty()

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'ARMATURE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "var_name")

    def execute(self, context):
        remove_variation(bpy.context.object, self.var_name)
        return {'FINISHED'}


def create_visibility_drivers(obj, arm, prop_name, value):
    for path in ("hide", "hide_render"):
        driver = obj.driver_add(path)
        driver.driver.expression = 'vis != %s' % value
        vis_var = driver.driver.variables.new()
        vis_var.name = "vis"
        vis_var.type = "SINGLE_PROP"
        target = vis_var.targets[0]
        target.id = arm
        target.data_path = '["%s"]' % prop_name

def find_bone_children(arm, bone_name):
    return [child for child in arm.children if child.parent_bone == bone_name]

class OBJECT_OT_add_new_plane_variations(Operator):
    """Parent planes to bones"""
    bl_idname = "lfs.add_new_plane_variations"
    bl_label = "Add new plane variations"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        arm = context.object
        planes = sorted(context.selected_objects, key=lambda obj: obj.name)
        planes.remove(arm)
        # plane = plane[0]
        pbone = context.active_pose_bone
        if not pbone.name.startswith("DEF-"):
            self.report({"ERROR"}, 'Bone name must start with "DEF-"')
            return {'CANCELLED'}

        # Check if custom prop exists in armature object, else create it
        prop_name = "variation_{}".format(pbone.name[4:])
        # Set up custom properties
        if not prop_name in arm:
            prop = rna_idprop_ui_prop_get(arm, prop_name, create=True)
            arm[prop_name] = 0
            prop["soft_min"] = 0
            prop["soft_max"] = 0
            prop["min"] = 0
            prop["max"] = 0

            # Find existing child, create driver on it
            child = find_bone_children(arm, pbone.name)[0]
            create_visibility_drivers(child, arm, prop_name, 0)
        else:
            prop = rna_idprop_ui_prop_get(arm, prop_name)

        # Do the parenting
        initial_position = arm.data.pose_position
        arm.data.pose_position = 'REST'
        context.scene.update()

        grp = arm.users_group[0]

        for plane in planes:
            prop["soft_max"] += 1
            prop["max"] += 1

            do_parenting(arm, pbone, plane, grp)

            # Create driver
            create_visibility_drivers(plane, arm, prop_name, prop["max"])
            for group in arm.users_group:
                if not plane.name in group.objects:
                    group.objects.link(plane)
        arm.data.pose_position = initial_position

        return {'FINISHED'}

def get_prop_value(obj):
    for driver in obj.animation_data.drivers:
        if driver.driver.variables[0].name == 'vis':
            break
    if driver:
        prop_value = int(re.findall('[0-9]', driver.driver.expression)[0])
        return prop_value

def set_prop_value(obj, prop_value):
    for driver in obj.animation_data.drivers:
        if driver.driver.variables[0].name == 'vis':
            # prop_value = int(re.findall('[0-9]', driver.driver.expression)[0])
            driver.driver.expression = "vis != %s" % prop_value

class OBJECT_OT_remove_plane_variation(Operator):
    """Parent planes to bones"""
    bl_idname = "lfs.remove_plane_variation"
    bl_label = "Remove plane variations"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type != 'ARMATURE'

    def execute(self, context):
        planes = context.selected_objects

        for plane in planes:
            arm = plane.parent
            if not arm.type == "ARMATURE":
                self.report({"WARNING"}, "Object %s is not the child of an armature" % plane.name)
                continue
            if not plane.animation_data and not plane.animation_data.drivers:
                self.report({"WARNING"}, "No driver found for object %s" % plane.name)
                continue

            # Get prop value in vis driver
            prop_value = get_prop_value(plane)

            # Delete drivers
            for driver in plane.animation_data.drivers:
                if driver.data_path.startswith('hide'):
                    plane.driver_remove(driver.data_path)
            plane.hide = False
            plane.hide_render = False

            # The next lines are a bad idea, leaving them for reference
            # If one removes a variation and slides bigger ones down, animation is messed up...
            # TODO I need to find empty variations instead

            # # Decrement other children's values
            # pbone = plane.parent_bone
            # siblings = find_bone_children(arm, pbone).remove(plane)
            # if siblings:
            #     for other in siblings:
            #         other_val = get_prop_value(other)
            #         if other_val > prop_value:
            #             set_prop_value(other, other_val-1)

            # # Decrement max prop value
            # prop_name = "variation_{}".format(pbone[4:])
            # prop = rna_idprop_ui_prop_get(arm, prop_name)
            # prop["soft_max"] -= 1
            # prop["max"] -= 1

            # # Delete it if there are no variations
            # if prop["max"] == 0:

            #     del arm[prop_name]

            mat = plane.matrix_world
            plane.parent = None
            plane.matrix_world = mat

        return {'FINISHED'}


class OBJECT_OT_add_uuid(Operator):
    """Parent planes to bones"""
    bl_idname = "lfs.add_uuid"
    bl_label = "Add UUIDS"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        for obj in bpy.context.scene.objects:
            if not 'db_uuid' in obj:
                obj['db_uuid'] = str(uuid4())

        for txt in bpy.data.texts:
            if txt.name.startswith('rig_ui') and not 'db_uuid' in txt:
                txt['db_uuid'] = str(uuid4())

        for grp in bpy.data.groups:
            if not 'db_uuid' in grp:
                grp['db_uuid'] = str(uuid4())

        return {'FINISHED'}



class OBJECT_OT_unparent_planes_from_bones(Operator):
    """Parent planes to bones"""
    bl_idname = "lfs.unparent_planes_from_bones"
    bl_label = "Unparent planes from bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        unparent_planes_from_bones(self, context)

        return {'FINISHED'}


class VIEW3D_PT_parent_planes_to_bones(bpy.types.Panel):
    bl_label = "Parent planes to bones"
    bl_category = 'Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = "LFS"


    # @classmethod
    # def poll(self, context):
    #     return context.object and context.object.type == 'ARMATURE'

    def draw(self, context):
        obj = context.active_object
        col = self.layout.column(align=True)
        # col.active = obj is not None
        col.operator("lfs.parent_planes_to_bones")
        col.operator("lfs.unparent_planes_from_bones")
        col = self.layout.column(align=True)
        col.operator("lfs.add_new_plane_variations")
        col.operator("lfs.remove_plane_variation")
        col = self.layout.column(align=True)
        col.operator("lfs.add_uuid")


class VIEW3D_PT_rig_plane_variations(bpy.types.Panel):
    bl_label = "Rig Plane Variations"
    bl_category = 'Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'ARMATURE' and "rig_id" in context.object.data

    def draw(self, context):
        obj = context.object
        col = self.layout.column(align=True)
        var_num = 0
        for p in obj.keys():
            if p.startswith('variation_'):
                col.prop(obj, '["%s"]' % p, text=p[10:])
                var_num += 1
        if not var_num:
            col.label("No variation found")
            col.label("for this rig.")

        col = self.layout.column(align=True)
        col.operator("lfs.delete_variation")


def register():
    bpy.utils.register_module(__name__)
    # bpy.utils.register_class(OBJECT_OT_parent_planes_to_bones)
    # bpy.utils.register_class(OBJECT_OT_unparent_planes_from_bones)
    # bpy.utils.register_class(OBJECT_OT_add_new_plane_variations)
    # bpy.utils.register_class(OBJECT_OT_remove_plane_variation)
    # bpy.utils.register_class(VIEW3D_PT_parent_planes_to_bones)
    # bpy.utils.register_class(VIEW3D_PT_rig_plane_variations)


def unregister():
    bpy.utils.unregister_module(__name__)
    # bpy.utils.unregister_class(OBJECT_OT_parent_planes_to_bones)
    # bpy.utils.unregister_class(OBJECT_OT_unparent_planes_from_bones)
    # bpy.utils.unregister_class(OBJECT_OT_add_new_plane_variations)
    # bpy.utils.unregister_class(OBJECT_OT_remove_plane_variation)
    # bpy.utils.unregister_class(VIEW3D_PT_parent_planes_to_bones)
    # bpy.utils.unregister_class(VIEW3D_PT_rig_plane_variations)


if __name__ == "__main__":
    register()
