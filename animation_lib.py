# Copyright (C) 2017 Les Fees Speciales
# voeu@les-fees-speciales.coop
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


bl_info = {
    "name": "Animation Lib",
    "description": "",
    "author": "Les Fées Spéciales",
    "version": (0, 0, 1),
    "blender": (2, 77, 0),
    "location": "View3D",
    "wiki_url": "",
    "category": "LFS"
    }

import bpy
import os
import glob
import re
import subprocess
from dil_utils import file_utils, movie_utils
from bpy.props import EnumProperty, StringProperty, BoolProperty
from bpy.types import AddonPreferences


def export_animation(op, obj, root):
    # get pantin type, family, name
    # asset_type = obj['asset_type']
    # asset_family = obj['asset_family']
    # asset_name = obj['asset_name']
    actor_filepath = obj['lib_path']

    # construct action_name
    if not op.anim_name:
        op.report({"ERROR"}, "Please choose a name")
        return {"CANCELLED"}
    action_name = 'LIB_animation_{anim_type}-{anim_name}'.format(
        # at=asset_type,
        # af=asset_family,
        # an=asset_name,
        anim_name=bpy.path.clean_name(op.anim_name).replace('_', '-'),
        anim_type=op.anim_type)
    print('action_name:', action_name)

    # set action.name
    obj.animation_data.action.name = action_name

    bpy.ops.wm.save_mainfile()

    # # construct actor_filepath
    # actor_filepath = os.path.join(
    #     root,
    #     'LIB_{at}_{af}_{an}_actor_REF.blend'.format(
    #         at=asset_type, af=asset_family, an=asset_name))

    print('actor_filepath:', actor_filepath)
    # construct anim_filepath
    anim_filepath = os.path.join(
        root,
        'animations',
        '{action_name}_v01.blend'.format(
            # at=asset_type,
            # af=asset_family,
            # an=asset_name,
            action_name=action_name))
    anim_filepath = file_utils.get_latest_version_by_number(anim_filepath)[1]
    print('anim_filepath:', anim_filepath)
    os.makedirs(os.path.dirname(anim_filepath), exist_ok=True)

    script = ("""
import bpy
#Set preferences
bpy.context.user_preferences.filepaths.use_load_ui = True
bpy.context.user_preferences.filepaths.save_version = 0

# Link in action from other file
with bpy.data.libraries.load('{this}', link=False) as (data_from, data_to):
    for a in data_from.actions:
        if a == '{action_name}':
            data_to.actions.append(a)
# bpy.data.actions[0].use_fake_user = True
object = bpy.data.objects['{asset_name}']
object.animation_data.action = bpy.data.actions[0]

bpy.ops.wm.save_as_mainfile(filepath="{anim}")
""").format(this=bpy.data.filepath,
            anim=anim_filepath,
            action_name=action_name,
            asset_name=obj.name)

    if op.do_blast:  # BLAST !
        render_filepath = os.path.join(root,
                                       'blasts',
                                       action_name)
        script += """
from math import pi
print("DOING BLAST...")
scene = bpy.context.scene
camera = bpy.data.cameras.new('CAM')
camera = bpy.data.objects.new('CAM', camera)
camera.rotation_euler = (pi/2, 0.0, 0.0)
scene.objects.link(camera)
scene.camera = camera
scene.render.filepath = '{render_filepath}'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.use_file_extension = True
# scene.render.ffmpeg.format = 'QUICKTIME'
scene.render.resolution_x = 940
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.frame_start, scene.frame_end = object.animation_data.action.frame_range
print(scene.frame_start, scene.frame_end)
for obj in object.children:
    obj.hide_select = False
    obj.select = True
bpy.ops.view3d.camera_to_view_selected()
#  TODO: parent camera to pantin's root
bpy.ops.render.render(animation=True)
print(scene.render.filepath)
""".format(render_filepath=render_filepath)

    args = ['blender', '-b', actor_filepath, '--python-expr', script]
    # print(blend_script)
    sp = subprocess.Popen(args, stderr=subprocess.PIPE)
    out, err = sp.communicate()
    if err:
        print("Could not setup file: %s\n%s" % (anim_filepath, err.decode('utf-8')))
    # CONVERT BLAST
    if op.do_blast:
        input_dir, image_name = os.path.split(render_filepath)
        movie_utils.convert_images(input_dir, image_name, input_dir, image_name,
                           frame_rate=24, frame_start=1, input_extension='png')
        del_dir = os.path.join(input_dir, image_name + "*" + '.png')
        for img in glob.glob(del_dir):
            print(img)
            print(os.path.join(del_dir, img))
            os.remove(os.path.join(del_dir, img))
        movie_utils.play_file(os.path.join(input_dir, image_name+'.mov'))


def default_anim_name(obj):
    """Try to get name from object's action's name."""
    last_uscore = obj.animation_data.action.name.split('_')
    if len(last_uscore) > 1:
        last_uscore = last_uscore[-1]
        split_name = last_uscore.split('-')
        if len(split_name) > 1:
            return split_name[0], '-'.join(split_name[1:])
        else:
            return "fixe", ""
    else:
        return "fixe", ""


class SaveAnimation(bpy.types.Operator):
    bl_idname = "lfs.animation_lib_save_animation"
    bl_label = "Save Animation"
    bl_description = ""
    bl_options = {"REGISTER"}

    type_items = (('fixe', 'Fixe', 'Fixe'),
                  ('marche', 'Marche', 'Marche'),
                  ('course', 'Course', 'Course'),
                  ('action', 'Action', 'Action'),
                  )
    anim_name = StringProperty(name='Name', default="")
    anim_type = EnumProperty(items=type_items, default="fixe", name='Type')
    do_blast = BoolProperty(default=True, name='Do Blast')

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.animation_data is not None)

    def invoke(self, context, event):
        self.anim_type, self.anim_name = default_anim_name(context.object)
        return bpy.context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "anim_name")
        col.prop(self, "anim_type")
        col.prop(self, "do_blast")
        col.label(text="This file will be saved", icon='ERROR')

    def execute(self, context):
        # self.anim_name = re.sub('[_ ]', '-', self.anim_name).lower()
        self.anim_name = bpy.path.clean_name(self.anim_name, replace='-').lower()

        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        lib_path = addon_prefs.lib_path

        export_animation(self, context.object, lib_path)
        return {"FINISHED"}


def get_pantin_anims(obj):
    """List animation blends in asset's library."""
    # if 'asset_name' in obj:
        # get pantin type, family, name
        # asset_type = obj['asset_type']
        # asset_family = obj['asset_family']
        # asset_name = obj['asset_name']

    # anim_dirpath = os.path.join(
    #     root,
        # '{at}/{af}/{an}/animation/'.format(
        #     at=asset_type,
        #     af=asset_family,
        #     an=asset_name,))

    user_preferences = bpy.context.user_preferences
    addon_prefs = user_preferences.addons[__name__].preferences
    lib_path = addon_prefs.lib_path
    lib_path = os.path.join(lib_path, 'animations')

    if not os.path.isdir(lib_path):
        return dict()
    anims = {f.split('_')[-2]: os.path.join(lib_path, f)
             for f in sorted(os.listdir(lib_path))
             if f.endswith('.blend')
             }
    return anims
    # return {anim: os.path.join(anim_dirpath, anim) for anim in anims}
    # else:
    #     return dict()


def import_animation(op, obj):
    anim_path = get_pantin_anims(obj)[op.anim_name]
    with bpy.data.libraries.load(anim_path, link=False) as (data_from, data_to):
        data_to.actions = data_from.actions[:1]  # get only first action...
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = data_to.actions[0]
    # TODO: import armature, apply transforms, delete armature

class ImportAnimation(bpy.types.Operator):
    bl_idname = "lfs.animation_lib_import_animation"
    bl_label = "Import Animation"
    bl_description = ""
    bl_options = {"REGISTER"}

    anim_name = StringProperty(name='Name', default="")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        import_animation(self, context.object)
        return {"FINISHED"}


class AnimationLibPanel(bpy.types.Panel):
    bl_idname = "lfs.animation_lib_panel"
    bl_label = "Animation Lib"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "LFS"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        if not bpy.data.filepath:
            layout.label(text='Please save file first', icon='ERROR')
        col = layout.column(align=True)
        col.operator('lfs.animation_lib_save_animation')

        anims = get_pantin_anims(context.object).keys()
        if anims:
            layout.separator()
            col = layout.column(align=True)
            col.label(text='Import...')
            for anim in sorted(anims):
                col.operator('lfs.animation_lib_import_animation',
                             text=anim.capitalize()).anim_name = anim


class AnimationLibPreferences(AddonPreferences):
    bl_idname = __name__

    # lfs_mode = bpy.props.BoolProperty(name="LFS Mode",
    #                                   default=False)
    # lib_paths = bpy.props.CollectionProperty(
    #         name="LIB Paths",
    #         type=bpy.types.PropertyGroup,
    #         )
    # active_lib = bpy.props.IntProperty(name="Active Lib",
    #                                    update=update_asset)
    lib_path = bpy.props.StringProperty(name="Lib Path", subtype='DIR_PATH')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "lib_path")




def register():
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
