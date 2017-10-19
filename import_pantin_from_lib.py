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
    "name": "Import Pantin From LIB",
    "description": "Set up a pantin character from a folder on disk.",
    "author": "Les Fees Speciales",
    "version": (0, 0, 1),
    "blender": (2, 79, 0),
    "location": "View3D",
    "wiki_url": "",
    "category": "LFS"
}

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty
import sys
import os
import re
import json
from uuid import uuid4


# Will I ever need this?
def get_object_by_uuid(objects, db_uuid, asset_uuid=None):
    for obj in objects:
        if obj.get('db_uuid') == db_uuid:
            if asset_uuid == obj.get('asset_uuid') or asset_uuid is None:
                return obj


def get_object_list_by_uuids(objects, uuids):
    ret_objs = []
    for obj in objects:
        if obj.get('db_uuid') in uuids:
            ret_objs.append(obj)
    return ret_objs


def reassign_duplicate_images(obj_group):
    """ Lists image textures in obj_groups, and reassigns textures
    if some of them share the same path.
    """
    images = {}  # filepath: image_name
    for i in bpy.data.images:
        if i.filepath in images:
            images[i.filepath].append(i)
        else:
            images[i.filepath] = [i]
    for i in images:
        images[i] = sorted(images[i], key=lambda i: i.name)
    for o in obj_group:
        if (o.data is None
                or not hasattr(o.data, 'materials')
                or o.data.materials is None):
            continue
        for m in o.data.materials:
            for t in m.texture_slots:
                if t is not None and t.texture.image is not None:
                    t.texture.image = images[t.texture.image.filepath][0]


def strip_numbers(name):
    """ Returns the name with trailing numbers stripped from it.
    """
    # regexp = re.compile("\.[0-9]+$")
    matches = re.findall("\.[0-9]+$", name)
    if matches:
        return name[:-len(matches[-1])]
    else:
        return name


def add_object_to_group(obj, group_name):
    if not group_name in bpy.data.groups:
        group = bpy.data.groups.new(group_name)
    else:
        group = bpy.data.groups[group_name]
    group.objects.link(obj)


def create_datablock(item, obj, id_type):
    """ Create the
    """
    obj_block = item.datablocks.add()
    obj_block.name = obj.get('db_uuid')
    obj_block.db_name = obj.name
    obj_block.id_type = id_type


def import_asset(self, context,
                 lib_path, asset_name,
                 new_asset_uuid=None):
    """ Given asset info, import it from the PRODUCTION drive.
    """
    print(asset_name)
    # hack for embedded nullbyte character
    asset_name = asset_name.replace('\x00', '')

    path = os.path.join(lib_path, asset_name, 'actor')

    for i in os.listdir(path):
        if i.endswith('_REF.blend'):
            path = os.path.join(path, i)
            break

    # path = os.path.join(REMOTE[sys.platform], path)
    print(path)
    # assets = glob.glob(path)
    # if assets:
    #     assets.sort()
    # else:
    #     if self.callback_idx:
    #         bpy.ops.lfs.message_callback(callback_idx=self.callback_idx, message=json.dumps({'Exception':'File not found'}))
    #     raise ImportError('File not found')
    # other = assets[-1]

    other = path

    # # Import scene and copy imported_items info
    # with bpy.data.libraries.load(other, link=False) as (data_from, data_to):
    #     data_to.scenes = data_from.scenes
    # original_scene = data_to.scenes[0]
    # if original_scene.imported_items:
    #     for i in original_scene.imported_items:
    #         pass

    # original_scene.user_clear()
    # bpy.data.scenes.remove(original_scene)

    # Link in groups and relevant texts from other file
    with bpy.data.libraries.load(other, link=False) as (data_from, data_to):
    #    print(data_from.groups)
        for g in data_from.groups:
            if g == asset_name:
                data_to.groups.append(g)
        for t in data_from.texts:
            if t.startswith('rig_ui'):
                data_to.texts.append(t)
        grps = data_to.groups
        txts = data_to.texts

    # print(list(zip(data_to.groups, [g for g in grps])))
    if len(grps) == 0:
        # if self.callback_idx:
        #     bpy.ops.lfs.message_callback(
        #         callback_idx=self.callback_idx,
        #         message=json.dumps({'Exception': "No group found in file"}))
        raise ImportError("No group found in file")

    # Generate new uuid if none was specified (ie. first import)
    if new_asset_uuid is None:
        new_asset_uuid = str(uuid4())

    # Deselect all objects
    for o in context.scene.objects:
        o.select = False

    # Dict for assets present in original blend file (recursive assets)
    # In that case a new uuid is appended to the original one and
    # only the present one is compared upon reloading
    original_assets = {}  # {asset_uuid: {'asset_name': ..., }}
    other_assets = []  # grp: [objs]

    # Instantiate each object
    for grp in grps:
        grp['asset_uuid'] = new_asset_uuid
        # grp_block = new_item.datablocks.add()
        # try:
        #     grp_block.name = grp.get('db_uuid')
        # except:
        #     print("Could not find uuid in", grp.name)
        #     self.report({"ERROR"}, "Could not find uuid in {}".format(grp.name))
        # grp_block.db_name = grp.name
        # grp_block.id_type = 'Group'

        for o in grp.objects:
            # print(o.name)
            context.scene.objects.link(o)

            # Place at cursor
            if not o.parent:
                o.location += context.scene.cursor_location

            # If the imported asset already has an uuid,
            # it was already part of an asset.
            # We reconstruct it based on the object props
            # [linking the scene would be too much of a hassle]
            if 'asset_uuid' in o:
                if not o['asset_uuid'] in original_assets:
                    original_assets[o['asset_uuid']] = {
                        'asset_name': o['asset_name'],
                        'lib_path': o['lib_path'],
                        'objects': [o],
                    }
                else:
                    original_assets[o['asset_uuid']]['objects'].append(o)
                o['asset_uuid'] += ' ' + new_asset_uuid
            else:
                other_assets.append(o)
                other_grp = grp.name
                # if grp in other_assets:
                #     other_assets[grp].append(o)
                # else:
                #     other_assets[grp] = [o]
                # other_assets.append(o)

                # Assign props.
                # They will be read back if the asset is used recursively.
                o['asset_uuid'] = new_asset_uuid
                o['asset_name'] = asset_name
                o['lib_path'] = lib_path

            # if o.type == "ARMATURE":
            #     context.scene.objects.active = o
            # add_object_to_group(o, asset_family.upper())

    if original_assets:
        for uuid, props in original_assets.items():
            group = bpy.data.groups.new(props['asset_name'])
            group['db_uuid'] = str(uuid4())

            new_item = context.scene.imported_items.add()
            new_item.name = group.name
            new_item.asset_name = props['asset_name']
            new_item.lib_path = props['lib_path']
            new_item.asset_uuid = uuid + ' ' + new_asset_uuid

            create_datablock(new_item, group, 'Group')

            for o in props['objects']:
                group.objects.link(o)
                create_datablock(new_item, o, 'Object')
                # o['asset_uuid'] = uuid + ' ' + new_asset_uuid

    if other_assets:
        new_item = context.scene.imported_items.add()
        new_item.name = other_grp
        new_item.asset_name = asset_name
        new_item.lib_path = lib_path
        new_item.asset_uuid = new_asset_uuid
        for o in other_assets:
            create_datablock(new_item, o, 'Object')

    def run_blender_script(text_block):
        '''from http://blender.stackexchange.com/a/31398/4979'''
        ctx = bpy.context.copy()
        ctx['edit_text'] = text_block
        bpy.ops.text.run_script(ctx)

    for txt in txts:
        text_parts = txt.name.split('.')
        if text_parts[-1].isdigit() and text_parts[-2] == 'py':
            text_parts = text_parts[:-2] + [text_parts[-1]] + [text_parts[-2]]
            while '.'.join(text_parts) in bpy.data.texts:
                text_parts[-2] = '{:03}'.format(int(text_parts[-2]) + 1)
            txt.name = '.'.join(text_parts)
        # needs to endwith(".py") to be registered
        # if not txt.name.endswith('.py'):
        #     txt.name += ".py"
        txt['asset_uuid'] = new_asset_uuid
        create_datablock(new_item, txt, 'Text')
        run_blender_script(txt)

    # reassign_duplicate_images(grp.objects)
    pantin_select(self, context, item=new_item)
    return new_item


class ImportPantinFromLIB(bpy.types.Operator):
    bl_idname = "lfs.import_pantin_from_lib"
    bl_label = "Add Asset"
    bl_options = {'REGISTER', 'UNDO'}

    # callback_idx = bpy.props.StringProperty(default='', options={"HIDDEN"})

    lib_path = bpy.props.StringProperty()
    asset_name = bpy.props.StringProperty()

    def execute(self, context):
        import_asset(self, context,
                     self.lib_path,
                     self.asset_name)

        return {'FINISHED'}

######################
#
#    Operators
#
######################


def pantin_select(self, context, item=None):
    imported_items = context.scene.imported_items
    if item is None:
        item = imported_items[self.item]
    # Deselect scene objects
    for o in context.scene.objects:
        o.select = False
    for db in item.datablocks:
        if db.id_type == "Object":
            try:
                obj = bpy.data.objects[db.db_name]
                obj.select = True
                if obj.type == "ARMATURE":
                    context.scene.objects.active = obj
            except KeyError:
                self.report({"ERROR"}, "Object %s was deleted." % db.db_name)


class PantinSelect(bpy.types.Operator):
    bl_idname = "lfs.pantin_select"
    bl_label = "Select"
    bl_description = "Select"
    bl_options = {"REGISTER"}

    item = bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        print("Selecting " + self.item)
        pantin_select(self, context)
        return {"FINISHED"}


def list_constraints(obj):
    """ List other objects constrained to obj.
    """
    constraints = []
    for oo in bpy.data.objects:
        if oo.constraints is not None:
            for con in oo.constraints:
                if hasattr(con, 'target') and con.target == obj:
                    # if obj in constraints:
                        constraints.append(con)
                    # else:
                    #     constraints[obj] = [con]
        if oo.type == 'ARMATURE':
            for bone in oo.pose.bones:
                if bone.constraints is not None:
                    for con in bone.constraints:
                        if hasattr(con, 'target') and con.target == obj:
                            # if obj in constraints:
                                constraints.append(con)
    return constraints


class PantinMoveLayer(bpy.types.Operator):
    bl_idname = "lfs.pantin_move_layer"
    bl_label = "Move Selected To Layers"
    bl_description = "Move selected objects to layers"
    bl_options = {"REGISTER"}

    dest_layers = bpy.props.BoolVectorProperty(
        size=20,
        name="Destination layers",
        description="Layers to move items to",
        subtype='LAYER')

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        if context.object is not None:
            self.dest_layers = context.object.layers
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        # Get selected item uuids
        selected_items = set()
        other_objects = []
        for o in context.selected_objects:
            if 'asset_uuid' in o:
                selected_items.add(o['asset_uuid'])
            else:
                other_objects.append(o)
        selected_items = [ii for ii in context.scene.imported_items
                          if ii.asset_uuid in selected_items]

        # Move it
        for i in selected_items:
            for db in i.datablocks:
                if db.id_type == 'Object':
                    if db.db_name in bpy.data.objects:
                        o = bpy.data.objects[db.db_name]
                        o.layers = self.dest_layers
                    else:
                        print(i.name, db.db_name, ": IMPOSSIBRU")
        for o in other_objects:
            o.layers = self.dest_layers
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        split = layout.split(0.3)
        t = split.label(text="Layer")
        r = split.row()

        col1 = r.column(align=True)
        row = col1.row(align=True)
        row.prop(self, "dest_layers", index=0, toggle=True, text="")
        row.prop(self, "dest_layers", index=1, toggle=True, text="")
        row.prop(self, "dest_layers", index=2, toggle=True, text="")
        row.prop(self, "dest_layers", index=3, toggle=True, text="")
        row.prop(self, "dest_layers", index=4, toggle=True, text="")

        col2 = r.column(align=True)
        row = col2.row(align=True)
        row.prop(self, "dest_layers", index=5, toggle=True, text="")
        row.prop(self, "dest_layers", index=6, toggle=True, text="")
        row.prop(self, "dest_layers", index=7, toggle=True, text="")
        row.prop(self, "dest_layers", index=8, toggle=True, text="")
        row.prop(self, "dest_layers", index=9, toggle=True, text="")

        row = col1.row(align=True)
        row.prop(self, "dest_layers", index=10, toggle=True, text="")
        row.prop(self, "dest_layers", index=11, toggle=True, text="")
        row.prop(self, "dest_layers", index=12, toggle=True, text="")
        row.prop(self, "dest_layers", index=13, toggle=True, text="")
        row.prop(self, "dest_layers", index=14, toggle=True, text="")

        row = col2.row(align=True)
        row.prop(self, "dest_layers", index=15, toggle=True, text="")
        row.prop(self, "dest_layers", index=16, toggle=True, text="")
        row.prop(self, "dest_layers", index=17, toggle=True, text="")
        row.prop(self, "dest_layers", index=18, toggle=True, text="")
        row.prop(self, "dest_layers", index=19, toggle=True, text="")


class PantinReload(bpy.types.Operator):
    """ This allows to reload an asset.
    - Constructs a dict of datablocks in the old imported_item
    - Imports the asset again (import_asset), from the info stored in the item
    - Copies transforms, parenting, etc.
    - Copies data block names
    - Copies active variations
    - Deletes the old datablocks
    """
    bl_idname = "lfs.pantin_reload"
    bl_label = "Reload"
    bl_description = "Reload"
    bl_options = {"REGISTER", "UNDO"}

    # callback_idx = bpy.props.StringProperty(default='', options={"HIDDEN"})

    item = bpy.props.StringProperty(default="", options={"HIDDEN"})
    # reload_objects = bpy.props.BoolProperty(name="Reload Missing Objects", default=False, )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)
        # return wm.invoke_props_dialog(self)

    def execute(self, context):
        print("Reloading " + self.item)
        imported_items = context.scene.imported_items

        old_item = imported_items[self.item]
        old_name = self.item
        # old_names = {(strip_numbers(odb.db_name), odb.id_type): odb for odb in old_item.datablocks}
        old_uuids = {odb.name: odb for odb in old_item.datablocks}

        # Import new asset based on old one's data
        (asset_name, lib_path, asset_uuid) = (old_item.asset_name, old_item.lib_path, old_item.asset_uuid)
        # Get only last part (local) of uuid
        asset_uuid = asset_uuid.split(" ")[-1]
        new_item = import_asset(self,
                                context, lib_path, asset_name,
                                new_asset_uuid=asset_uuid)
        new_item_name = new_item.name  # for pointer change later (?)
        old_item.name = old_name
        old_item = imported_items[old_name]  # oh ffs
        # new_names = {strip_numbers(ndb.db_name): ndb for ndb in new_item.datablocks}

        # Reload variations
        list_textures(self, context, new_item)
        if old_item.variations:
            new_item.active_variation = old_item.active_variation

        for db in new_item.datablocks:
            block_name = db.name
            try:
                old_db = old_uuids[block_name]
            except:
                # TODO catch error
                continue

            if db.id_type == "Group":
                if old_db.db_name in bpy.data.groups:
                    old_grp = bpy.data.groups[old_db.db_name]
                    new_grp = bpy.data.groups[db.db_name]
                    # renaming data blocks
                    tmp_name = old_grp.name
                    old_grp.name += ".DEL"  # tmp_name
                    new_grp.name = tmp_name  # old_grp.name
                    db.db_name = tmp_name
                    old_db.db_name = old_grp.name
            elif db.id_type == "Text":
                if old_db.db_name in bpy.data.texts:
                    old_txt = bpy.data.texts[old_db.db_name]
                    new_txt = bpy.data.texts[db.db_name]
                    # renaming data blocks
                    tmp_name = old_txt.name
                    old_txt.name += ".DEL"  # tmp_name
                    new_txt.name = tmp_name  # old_txt.name
                    db.db_name = tmp_name
                    old_db.db_name = old_txt.name

            elif db.id_type == "Object":
                # variations
                if old_db.variations:
                    db.active_variation = old_db.active_variation
                    # print('VARS', db, ':', old_db.active_variation, db.active_variation)
                    # plane_update(db)

                if (db.db_name != old_db.db_name
                        and old_db.db_name in bpy.context.scene.objects):
                    print('DB:', db.db_name)
                    # copy transforms
                    old_obj = bpy.data.objects[old_db.db_name]
                    new_obj = bpy.data.objects[db.db_name]
                    if (old_obj.animation_data is not None
                            and old_obj.animation_data.action is not None):
                        new_obj.animation_data_create()
                        new_obj.animation_data.action = old_obj.animation_data.action
                    # parenting
                    if (old_obj.parent is not None
                            and old_obj.parent.name not in
                            [db.db_name for db in old_item.datablocks]):
                        print(old_obj.parent.name)
                        # old_parent_uuid = old_obj.parent['db_uuid']
                        # new_parent = new_item.datablocks[old_parent_uuid]
                        # new_obj.parent = bpy.data.objects[new_parent.name]
                        new_obj.parent = old_obj.parent
                        new_obj.parent_type = old_obj.parent_type
                        new_obj.parent_bone = old_obj.parent_bone
                        new_obj.matrix_local = old_obj.matrix_local
                    if old_obj.parent is None:
                        new_obj.matrix_local = old_obj.matrix_local

                    # reparent children to reloaded item
                    for child in old_obj.children:
                        if child.name not in [
                                db.db_name for db in old_item.datablocks
                                ]:
                            matrix_local = child.matrix_local.copy()
                            parent_bone = child.parent_bone
                            parent_type = child.parent_type
                            child.parent = new_obj
                            child.parent_type = parent_type
                            child.parent_bone = parent_bone
                            child.matrix_local = matrix_local

                    # constraints
                    for con in list_constraints(old_obj):
                        con.target = new_obj
                    for old_con in old_obj.constraints:
                        if not old_con.name in new_obj.constraints:
                            con = new_obj.constraints.new(old_con.type)
                            for at in dir(old_con):
                                try:
                                    setattr(con, at, getattr(old_con, at))
                                except:
                                    pass  # (...)
                    if old_obj.type == 'ARMATURE':
                        for pb in old_obj.pose.bones:
                            new_obj.pose.bones[pb.name].matrix_basis = pb.matrix_basis
                            for old_con in pb.constraints:
                                if not old_con.name in pb.constraints:
                                    con = new_obj.pose.bones[pb.name].constraints.new(old_con.type)
                                    for at in dir(old_con):
                                        try:
                                            setattr(con, at, getattr(old_con, at))
                                        except:
                                            pass # (...)

                    # renaming data blocks
                    tmp_name = old_obj.name
                    old_obj.name += ".DEL"  # tmp_name
                    new_obj.name = tmp_name  # old_obj.name
                    db.db_name = tmp_name
                    old_db.db_name = old_obj.name

                    if new_obj.data:
                        new_obj.data.name = old_obj.data.name
                        # print(new_obj.name)
                        for m_i, m_slot in enumerate(old_obj.material_slots):
                            # print(m_slot.material, new_obj.material_slots[m_i].material)
                            for t_i, t_slot in enumerate(m_slot.material.texture_slots):
                                # print(t_i, t_slot)
                                if t_slot is not None:
                                    new_obj.material_slots[m_i].material.texture_slots[t_i].texture.name = t_slot.texture.name
                            new_obj.material_slots[m_i].material.name = m_slot.material.name
                        new_obj['asset_uuid'] = old_item.asset_uuid

                else:  # old_db.db_name already not in bpy.data.objects
                    print('OLD:', old_db.db_name)
                    old_item.datablocks.remove(
                        old_item.datablocks.find(old_db.name))

        old_uuid = old_item.asset_uuid
        new_item.asset_uuid = old_uuid
        # bpy.ops.lfs.pantin_select(item=new_item.name)
        pantin_select(self, context, new_item)
        imported_items.update()
        # context.scene.update()
        print('TO DELETE:', old_item)
        pantin_delete(self, context, old_item)
        imported_items[new_item_name].name = self.item
        return {"FINISHED"}


def pantin_delete(self, context, item=None):
    # if context.object is not None:
    #     bpy.ops.object.mode_set(mode='OBJECT')
    imported_items = context.scene.imported_items
    # if item is not None:
    #     item = item
    # else:
    if item is None:
        item = imported_items[self.item]
    for db in item.datablocks:
        if db.id_type == "Object":
            try:
                obj = bpy.data.objects[db.db_name]
                if obj.name in context.scene.objects:
                    context.scene.objects.unlink(obj)
                obj.user_clear()
                bpy.data.objects.remove(obj)
            except KeyError:
                self.report(
                    {"ERROR"}, "Object %s was deleted already." % db.db_name
                )

        elif db.id_type == "Text":
            # print(db.db_name)
            try:
                txt = bpy.data.texts[db.db_name]
                txt.user_clear()
                bpy.data.texts.remove(txt)
            except KeyError:
                self.report(
                    {"ERROR"}, "Text %s was deleted already." % db.db_name
                )

        elif db.id_type == "Group":
            try:
                grp = bpy.data.groups[db.db_name]
                grp.user_clear()
                bpy.data.groups.remove(grp)
            except KeyError:
                self.report(
                    {"ERROR"}, "Group %s was deleted already." % db.db_name
                )

    item_index = imported_items.keys().index(self.item)
    imported_items.remove(item_index)


class PantinDelete(bpy.types.Operator):
    bl_idname = "lfs.pantin_delete"
    bl_label = "Delete"
    bl_description = "Delete"
    bl_options = {'REGISTER', 'UNDO'}

    item = bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        print("Deleting " + self.item)
        pantin_delete(self, context)
        return {"FINISHED"}


def get_image_texture_name(obj):
    if (obj.active_material is not None
            and obj.active_material.active_texture is not None
            and obj.active_material.active_texture.type == "IMAGE"
            and obj.active_material.active_texture.image is not None
            and obj.active_material.active_texture.image.filepath is not None):
        name = os.path.basename(
            obj.active_material.active_texture.image.filepath
        )
        return name


def list_textures(self, context, item=None):
    imported_items = context.scene.imported_items
    # if item is not None:
    #     item = imported_items[item]
    # else:
    if item is None:
        item = imported_items[self.item]

    asset_name = item.asset_name
    lib_path = item.lib_path

    dirpath = os.path.join(lib_path, asset_name, 'actor', 'textures')

    # hack for embedded nullbyte character
    dirpath = dirpath.replace('\x00', '')
    if not os.path.exists(dirpath):
        return
    files = os.listdir(dirpath)
    files = [os.path.basename(p) for p in files if p.endswith('.png')]
    if files:
        files.sort()
    # print(files)
    assets = {}
    rexp = re.compile("([a-zA-Z0-9_-]+)(_[A-Z]+)$")
    old_db_variation = {
        db.name: db.active_variation for db in item.datablocks
        if db.id_type == 'Object'
    }
    old_item_variation = item.active_variation
    # reset var, to have the initial filepaths for all textures
    item.active_variation = 0

    for db in item.datablocks:
        db.variations.clear()
    for file in sorted(files):
        file = os.path.splitext(file)[0]
        m = rexp.search(file)
        if m is None:
            assets[file] = [""]
            prefix = file
            suffix = ""
        else:
            prefix, suffix = m.groups()
            if not prefix.startswith('Joint'):
                try:
                    assets[prefix].append(suffix)
                except:
                    self.report({"ERROR"}, message="Error with file " + file)
                    raise
        for db in item.datablocks:
            if db.id_type == 'Object':
                try:
                    obj = bpy.data.objects[db.db_name]
                except KeyError:
                    continue
                img_name = get_image_texture_name(obj)
                if img_name and img_name[:-4] == prefix:
                    new_db_var = db.variations.add()
                    new_db_var.name = suffix
                    new_db_var.filepath = os.path.join(dirpath, file+'.png')

    variations = set()
    for ass in assets.values():
        # print(ass)
        variations.update(ass)
    item.variations.clear()
    for var in sorted(variations):
        new_item_var = item.variations.add()
        new_item_var.name = var

    # restore old variations
    item.active_variation = old_item_variation
    for db, active in old_db_variation.items():
        item.datablocks[db].active_variation = active


class PantinListTextures(bpy.types.Operator):
    bl_idname = "lfs.pantin_list_textures"
    bl_label = "List Textures"
    bl_description = "Refresh texture list"
    # bl_description = "List Textures"
    bl_options = {'REGISTER', 'UNDO'}

    item = bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        list_textures(self, context)

        return {"FINISHED"}


class PantinSetShadowVisibility(bpy.types.Operator):
    bl_idname = "lfs.pantin_set_shadow_visibility"
    bl_label = "Set Shadow Visibility"
    bl_description = "Set Shadow Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    do_hide = bpy.props.BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        for obj in bpy.data.objects:
            if (obj.name.lower().startswith("ombre")
                    and not obj.name.lower().startswith("ombrelle")):
                obj.hide = self.do_hide
                if not self.do_hide:
                    obj.hide_render = False

        return {"FINISHED"}


def update_asset(self, context):
    settings = context.scene.imported_items_settings
    user_preferences = context.user_preferences
    addon_prefs = user_preferences.addons[__name__].preferences
    lib_paths = addon_prefs.lib_paths

    settings.active_asset = 0
    settings.assets.clear()

    if len(lib_paths):
        lib_path = lib_paths[addon_prefs.active_lib].name
        for i in sorted(os.listdir(lib_path)):
            if os.path.isdir(
                os.path.join(lib_path, i)
            ):
                t = settings.assets.add()
                t.name = i

class PantinLibAdd(bpy.types.Operator):
    """
    """
    bl_idname = "lfs.pantin_lib_add"
    bl_label = "Add Lib"
    bl_description = "Add Lib"
    bl_options = {"REGISTER", "UNDO"}

    directory = StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})


    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        lib_paths = addon_prefs.lib_paths

        if not self.directory in lib_paths:
            lib = lib_paths.add()
            lib.name = self.directory

        update_asset(self, context)
        return {'FINISHED'}


class PantinLibRemove(bpy.types.Operator):
    """
    """
    bl_idname = "lfs.pantin_lib_remove"
    bl_label = "Remove Lib"
    bl_description = "Remove Lib"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        lib_paths = addon_prefs.lib_paths
        active_lib = addon_prefs.active_lib

        lib_paths.remove(active_lib)
        if active_lib > len(lib_paths) - 1:
            addon_prefs.active_lib = len(lib_paths) - 1
        update_asset(self, context)
        return {'FINISHED'}


######################
#
#    UI
#
######################


class CRIQUET_UL_variations_list(bpy.types.UIList):

    def draw_item(self, context,
                  layout, data,
                  item, icon,
                  active_data, active_propname):
        # arm = data
        # draw_item must handle the three layout types...
        # Usually 'DEFAULT' and 'COMPACT' can share the same code.
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon='FILE_IMAGE')
        # 'GRID' layout type should be as compact as possible
        # (typically a single icon!).
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class CRIQUET_UL_planes_list(bpy.types.UIList):
    def draw_item(self, context,
                  layout, data,
                  item, icon,
                  active_data, active_propname):
        if item.id_type == 'Object':
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                layout.prop(item, "db_name",
                            text="", emboss=False, icon='FILE_IMAGE')
            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon_value=icon)


class PantinsImportPanel(bpy.types.Panel):
    bl_idname = "lfs.pantins_import_panel"
    bl_label = "Import Pantins"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "LFS"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.imported_items_settings

        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences

        # Importer
        layout.label(text="Select asset:")
        row = layout.row()
        row.template_list("UI_UL_list",
                          "libs",
                          addon_prefs,
                          "lib_paths",
                          addon_prefs,
                          "active_lib",
                          rows=5)
        col = row.column(align = True)
        col.operator("lfs.pantin_lib_add", icon='ZOOMIN', text="")
        col.operator("lfs.pantin_lib_remove", icon='ZOOMOUT', text="")
        row.template_list("UI_UL_list",
                          "assets",
                          settings,
                          "assets",
                          settings,
                          "active_asset",
                          rows=5)
        row = layout.row()
        op = layout.operator("lfs.import_pantin_from_lib")
        if len(addon_prefs.lib_paths) and len(settings.assets):
            op.lib_path = addon_prefs.lib_paths[addon_prefs.active_lib].name
            op.asset_name = settings.assets[settings.active_asset].name
        else:
            row.active = False


class PantinsPanel(bpy.types.Panel):
    bl_idname = "lfs.pantins_panel"
    bl_label = "Pantins"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "LFS"

    def draw(self, context):
        layout = self.layout
        if len(context.scene.imported_items) == 0:
            layout.label(text="Nothing imported yet", icon="INFO")
        else:
            pantins_number = len(context.scene.imported_items)
            layout.label(
                text="{} pantin{} in scene".format(
                    pantins_number, "s" if pantins_number > 1 else ""))
            layout.operator("lfs.pantin_move_layer")
            row = layout.row(align=True)
            row.label(text="Shadow Visibility:")
            row.operator(
                "lfs.pantin_set_shadow_visibility",
                text="", icon="RESTRICT_VIEW_ON").do_hide = True
            row.operator(
                "lfs.pantin_set_shadow_visibility",
                text="", icon="RESTRICT_VIEW_OFF").do_hide = False
            layout.separator()
            layout.prop(
                context.scene.imported_items_settings, "show_only_active")
            if not context.scene.imported_items_settings.show_only_active:
                layout.prop(context.scene.imported_items_settings,
                            "pantins_panel_search", icon="VIEWZOOM", text="")

            for item in sorted(context.scene.imported_items, key=lambda i: i.name):
                if ((context.scene.imported_items_settings.show_only_active
                        and context.object is not None
                        and 'asset_uuid' in context.object
                        and context.object['asset_uuid'] != item.asset_uuid
                     )
                        or (
                        not context.scene.imported_items_settings.show_only_active
                        and context.scene.imported_items_settings.pantins_panel_search != ''
                        and not context.scene.imported_items_settings.pantins_panel_search.lower() in item.name.lower()
                        )
                    ):
                    continue
                box = layout.box()
                row = box.row()
                sub = row.row(align=True)
                if (context.object is not None
                        and 'asset_uuid' in context.object
                        and context.object['asset_uuid'] == item.asset_uuid):
                    sub.label(text='', icon='SMALL_TRI_RIGHT_VEC')
                sub.label(text=item.name)
                sub.prop(item,
                         "hide",
                         text="",
                         icon="RESTRICT_VIEW_ON"
                         if item.hide else "RESTRICT_VIEW_OFF")
                sub.prop(item,
                         "hide_select",
                         text="",
                         icon="RESTRICT_SELECT_ON"
                         if item.hide_select else "RESTRICT_SELECT_OFF")
                sub = row.row(align=True)
                sub.operator("lfs.pantin_select",
                             text="", icon="HAND").item = item.name
                sub.operator("lfs.pantin_reload",
                             text="", icon="FILE_REFRESH").item = item.name
                sub.operator("lfs.pantin_delete",
                             text="", icon="X").item = item.name

                col = box.column(align=True)
                col.prop(item, "local_variations")
                row = col.row()
                if item.local_variations:
                    col = row.column()
                    col.label(text="Plane:")
                    col.template_list("CRIQUET_UL_planes_list",
                                      item.name+'_planes',
                                      item,
                                      "datablocks",
                                      item,
                                      "active_datablock",
                                      rows=3)

                    col = row.column()
                    col.label(text="Variation:")
                    col.template_list("CRIQUET_UL_variations_list",
                                      item.name+'_variations',
                                      item.datablocks[item.active_datablock],
                                      "variations",
                                      item.datablocks[item.active_datablock],
                                      "active_variation",
                                      rows=3)
                else:
                    col = row.column()
                    col.label(text="Variation:")
                    col.template_list("CRIQUET_UL_variations_list",
                                      item.name+'_variations',
                                      item, "variations",
                                      item,
                                      "active_variation",
                                      rows=3)
                col = row.column()
                col.alignment = "EXPAND"
                col.label(text="")
                col.scale_x = 0.1
                col.scale_y = 1.5
                col.operator("lfs.pantin_list_textures",
                             text="",
                             icon="FILE_REFRESH").item = item.name


######################
#
#    Data structure
#
######################

object_id_type_items = (
    ('Object', '', 'Object'),
    ('Group', '', 'Group'),
    ('Text', '', 'Text'),
    )


class Texture_Variations(bpy.types.PropertyGroup):
    name = bpy.props.StringProperty(default='')
    filepath = bpy.props.StringProperty(default='')

bpy.utils.register_class(Texture_Variations)


def plane_update(db):
    if db.variations:
        suffix = db.variations[db.active_variation].name
        # print(suffix)
        if db.id_type == 'Object' and suffix in db.variations:
            separate_texture = True
            filepath = db.variations[suffix].filepath
            set_texture(bpy.data.objects[db.db_name],
                        filepath, separate_texture)
            # print(bpy.data.objects[db.name])
        # # print(self.variations[self.active_variation].name)


def plane_update_callback(self, context):
    plane_update(self)


class DataBlock(bpy.types.PropertyGroup):
    id_type = bpy.props.EnumProperty(name="ID Type",
                                     items=object_id_type_items,
                                     default='Object')
    name = bpy.props.StringProperty(default='')
    variations = bpy.props.CollectionProperty(name="Variations",
                                              type=Texture_Variations)
    active_variation = bpy.props.IntProperty(name="Active Variation",
                                             update=plane_update_callback)
    db_name = bpy.props.StringProperty(name="Datablock Name",
                                       default='')

bpy.utils.register_class(DataBlock)


def set_texture(obj, filepath, separate_texture=False):
    if obj.type == "MESH":
        if False:  # separate_texture: # Why did I do that, again?
            mesh = obj.data.copy()
            obj.data = mesh
            mesh.name = obj.name

            mat = obj.active_material.copy()
            obj.active_material = mat
            mat.name = obj.name

            tex = mat.active_texture.copy()
            mat.active_texture = tex
            tex.name = obj.name

            img = tex.image.copy()
            tex.image = img
            img.name = obj.name
        else:
            img = obj.active_material.active_texture.image
        img.filepath = filepath


def variation_update(self, context):
    if self.variations:
        suffix = self.variations[self.active_variation].name
        # print(suffix)
        for db in self.datablocks:
            if (db.id_type == 'Object'
                    and suffix in db.variations
                    and db.db_name in bpy.data.objects):
                var = db.variations[suffix]
                i = db.variations.values().index(var)
                db.active_variation = i
                filepath = var.filepath
                # print(db.name)
                set_texture(bpy.data.objects[db.db_name], filepath)
                # print(bpy.data.objects[db.name])
        # print(self.variations[self.active_variation].name)


def visibility_update(self, context):
    for db in self.datablocks:
        if db.id_type == 'Object':
            bpy.data.objects[db.db_name].hide = self.hide


def select_update(self, context):
    for db in self.datablocks:
        if (db.id_type == 'Object'
                and bpy.data.objects[db.db_name].type != 'ARMATURE'):
            bpy.data.objects[db.db_name].hide_select = self.hide_select


class Imported_Item(bpy.types.PropertyGroup):
    asset_uuid = bpy.props.StringProperty(name="Asset UUID", default='')
    lib_path = bpy.props.StringProperty(name="Asset Lib Path", default='')
    asset_name = bpy.props.StringProperty(name="Asset Name", default='')
    datablocks = bpy.props.CollectionProperty(name="Datablocks",
                                              type=DataBlock)
    variations = bpy.props.CollectionProperty(name="Variations",
                                              type=bpy.types.PropertyGroup)
    active_datablock = bpy.props.IntProperty(name="Active Datablock", )
    active_variation = bpy.props.IntProperty(name="Active Variation",
                                             update=variation_update)
    local_variations = bpy.props.BoolProperty(name="Local Variations", default=False, )
    hide = bpy.props.BoolProperty(name="Hide",
                                  description="Restrict/Allow visibility",
                                  default=False, update=visibility_update)
    hide_select = bpy.props.BoolProperty(
        name="Hide select",
        description="Restrict/Allow mesh selection",
        default=False,
        update=select_update)


class Imported_Items_Settings(bpy.types.PropertyGroup):
    show_only_active = bpy.props.BoolProperty(
        name="Show Only Active", default=False, )
    pantins_panel_search = bpy.props.StringProperty(
        name="Pantins Panel Search",
        default='',
        description="Search in Pantins")
    assets = bpy.props.CollectionProperty(name="Assets",
        type=bpy.types.PropertyGroup)
    active_asset = bpy.props.IntProperty(name="Active Asset")

class ImportPantinPreferences(AddonPreferences):
    bl_idname = __name__

    lib_paths = bpy.props.CollectionProperty(
            name="LIB Paths",
            type=bpy.types.PropertyGroup,
            )
    active_lib = bpy.props.IntProperty(name="Active Lib",
                                       update=update_asset)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.template_list("UI_UL_list",
                          "libs",
                          self,
                          "lib_paths",
                          self,
                          "active_lib",
                          rows=5)

        col = row.column(align=True)
        col.operator("lfs.pantin_lib_add", icon='ZOOMIN', text="")
        col.operator("lfs.pantin_lib_remove", icon='ZOOMOUT', text="")

def register():
    bpy.utils.register_class(Imported_Item)
    bpy.types.Scene.imported_items = bpy.props.CollectionProperty(
        name="Imported Items", type=Imported_Item)
    bpy.utils.register_class(Imported_Items_Settings)
    bpy.types.Scene.imported_items_settings = bpy.props.PointerProperty(
        name="Imported Items Settings", type=Imported_Items_Settings)
    bpy.utils.register_class(ImportPantinFromLIB)
    bpy.utils.register_class(PantinLibAdd)
    bpy.utils.register_class(PantinLibRemove)
    bpy.utils.register_class(CRIQUET_UL_variations_list)
    bpy.utils.register_class(CRIQUET_UL_planes_list)
    bpy.utils.register_class(PantinMoveLayer)
    bpy.utils.register_class(PantinsImportPanel)
    bpy.utils.register_class(PantinsPanel)
    bpy.utils.register_class(PantinSelect)
    bpy.utils.register_class(PantinReload)
    bpy.utils.register_class(PantinDelete)
    bpy.utils.register_class(PantinListTextures)
    bpy.utils.register_class(PantinSetShadowVisibility)
    bpy.utils.register_class(ImportPantinPreferences)


def unregister():
    del bpy.types.Scene.imported_items
    bpy.utils.unregister_class(DataBlock)
    bpy.utils.unregister_class(Imported_Item)
    bpy.utils.unregister_class(Imported_Items_Settings)
    bpy.utils.unregister_class(ImportPantinFromLIB)
    bpy.utils.unregister_class(PantinLibAdd)
    bpy.utils.unregister_class(PantinLibRemove)
    bpy.utils.unregister_class(CRIQUET_UL_variations_list)
    bpy.utils.unregister_class(CRIQUET_UL_planes_list)
    bpy.utils.unregister_class(PantinMoveLayer)
    bpy.utils.unregister_class(PantinsImportPanel)
    bpy.utils.unregister_class(PantinsPanel)
    bpy.utils.unregister_class(PantinSelect)
    bpy.utils.unregister_class(PantinReload)
    bpy.utils.unregister_class(PantinDelete)
    bpy.utils.unregister_class(PantinListTextures)
    bpy.utils.unregister_class(PantinSetShadowVisibility)
    bpy.utils.unregister_class(ImportPantinPreferences)

if __name__ == "__main__":
    register()

    # Test call
#    bpy.ops.lfs.criquet_add_asset(asset_name="F18P", asset_family="Pantin", asset_type="Chars")
