# window.py
#
# Copyright 2019 Romain F. T.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GLib

from .gi_composites import GtkTemplate

from .tool_arc import ToolArc
from .tool_circle import ToolCircle
from .tool_crop import ToolCrop
from .tool_experiment import ToolExperiment
from .tool_flip import ToolFlip
from .tool_freeshape import ToolFreeshape
from .tool_line import ToolLine
from .tool_paint import ToolPaint
from .tool_pencil import ToolPencil
from .tool_picker import ToolPicker
from .tool_polygon import ToolPolygon
from .tool_rectangle import ToolRectangle
from .tool_rotate import ToolRotate
from .tool_saturate import ToolSaturate
from .tool_scale import ToolScale
from .tool_select import ToolSelect
from .tool_text import ToolText

from .image import DrawingImage
from .properties import DrawingPropertiesDialog
from .utilities import utilities_save_pixbuf_at
from .minimap import DrawingMinimap
from .options_manager import DrawingOptionsManager
from .color_popover import DrawingColorPopover

@GtkTemplate(ui='/com/github/maoschanz/Drawing/ui/window.ui')
class DrawingWindow(Gtk.ApplicationWindow):
	__gtype_name__ = 'DrawingWindow'

	_settings = Gio.Settings.new('com.github.maoschanz.Drawing')

	# Window empty widgets
	tools_panel = GtkTemplate.Child()
	toolbar_box = GtkTemplate.Child()
	info_bar = GtkTemplate.Child()
	info_label = GtkTemplate.Child()
	notebook = GtkTemplate.Child()
	bottom_panel_box = GtkTemplate.Child()

	# Default bottom panel
	bottom_panel = GtkTemplate.Child()
	color_box = GtkTemplate.Child()
	color_menu_btn_l = GtkTemplate.Child()
	color_menu_btn_r = GtkTemplate.Child()
	l_btn_image = GtkTemplate.Child()
	r_btn_image = GtkTemplate.Child()
	thickness_spinbtn = GtkTemplate.Child()
	options_btn = GtkTemplate.Child()
	options_label = GtkTemplate.Child()
	options_long_box = GtkTemplate.Child()
	options_short_box = GtkTemplate.Child()
	minimap_btn = GtkTemplate.Child()
	minimap_icon = GtkTemplate.Child()
	minimap_label = GtkTemplate.Child()
	minimap_arrow = GtkTemplate.Child()

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.app = kwargs['application']
		self.init_template()

		self.header_bar = None
		self.main_menu_btn = None
		self.needed_width_for_long = 0

		if self._settings.get_boolean('maximized'):
			self.maximize()
		self.set_ui_bars()

	def init_window_content(self, gfile):
		"""Initialize the window's content, such as the minimap, the color popovers,
		the tools, their options, and a new default image."""
		self.hijacker_id = None
		self.tools = None
		self.minimap = DrawingMinimap(self, self.minimap_btn)
		self.options_manager = DrawingOptionsManager(self)
		self.image_list = []
		self.thickness_spinbtn.set_value(self._settings.get_int('last-size'))

		self.build_color_buttons()
		self.add_all_win_actions()
		self.build_new_tab(gfile)
		self.init_tools()
		self.connect_signals()
		self.set_picture_title()
		self.prompt_message(False, 'window successfully started')

	def set_cursor(self, is_custom):
		if is_custom:
			name = self.active_tool().cursor_name
		else:
			name = 'default'
		cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), name)
		self.get_window().set_cursor(cursor)

	def init_tools(self):
		"""Initialize all tools, building the UI for them including the menubar,
		and enable the default tool."""
		self.tools = {}
		self.tools['pencil'] = ToolPencil(self)
		self.tools['select'] = ToolSelect(self)
		self.tools['text'] = ToolText(self)
		self.tools['picker'] = ToolPicker(self)
		self.tools['paint'] = ToolPaint(self)
		self.tools['line'] = ToolLine(self)
		self.tools['arc'] = ToolArc(self)
		self.tools['rectangle'] = ToolRectangle(self)
		self.tools['circle'] = ToolCircle(self)
		self.tools['polygon'] = ToolPolygon(self)
		self.tools['freeshape'] = ToolFreeshape(self)
		if self._settings.get_boolean('devel-only'):
			self.tools['experiment'] = ToolExperiment(self)
		self.tools['crop'] = ToolCrop(self)
		self.tools['scale'] = ToolScale(self)
		self.tools['rotate'] = ToolRotate(self)
		self.tools['flip'] = ToolFlip(self)
		self.tools['saturate'] = ToolSaturate(self)

		# Buttons for tools (in the side panel and the selection tool action bar)
		self.build_tool_rows()

		# Global menubar
		if not self.app.has_tools_in_menubar:
			drawing_tools_section = self.app.get_menubar().get_item_link(4, \
				Gio.MENU_LINK_SUBMENU).get_item_link(0, Gio.MENU_LINK_SECTION)
			canvas_tools_section = self.app.get_menubar().get_item_link(4, \
				Gio.MENU_LINK_SUBMENU).get_item_link(1, Gio.MENU_LINK_SECTION).get_item_link(0, \
				Gio.MENU_LINK_SUBMENU).get_item_link(0, Gio.MENU_LINK_SECTION)
			for tool_id in self.tools:
				if self.tools[tool_id].is_hidden:
					self.tools[tool_id].add_item_to_menu(canvas_tools_section)
				else:
					self.tools[tool_id].add_item_to_menu(drawing_tools_section)
			self.app.has_tools_in_menubar = True

		# Initialisation of options and menus
		tool_id = self._settings.get_string('last-active-tool')
		if tool_id not in self.tools:
			tool_id = 'pencil'
		self.active_tool_id = tool_id
		self.former_tool_id = tool_id
		if tool_id == 'pencil':
			self.enable_tool(tool_id, True)
		else:
			self.active_tool().row.set_active(True)

	def build_new_image(self, *args):
		"""Open a new tab with a drawable blank image."""
		self.build_new_tab(None)
		self.set_picture_title()

	def build_new_tab(self, gfile):
		"""Open a new tab with an optional file to open in it."""
		new_image = DrawingImage(self)
		self.image_list.append(new_image)
		self.notebook.append_page(new_image, new_image.tab_title)
		if gfile is None:
			new_image.init_background()
		else:
			new_image.try_load_file(gfile)
		self.update_tabs_visibility()
		self.notebook.set_current_page(self.notebook.get_n_pages()-1)

	def close_tab(self, tab):
		"""Close a tab (after asking to save if needed)."""
		index = self.notebook.page_num(tab)
		if not self.image_list[index]._is_saved:
			self.notebook.set_current_page(index)
			is_saved = self.confirm_save_modifs()
			if not is_saved:
				return False
		self.notebook.remove_page(index)
		self.image_list.pop(index)
		self.update_tabs_visibility()
		return True

	def action_close(self, *args):
		self.close()

	def on_close(self, *args):
		"""Event callback when trying to close a window. It saves/closes each
		tab and saves the current window settings in order to restore them."""
		for i in self.image_list:
			if not self.close_tab(i):
				return True

		self._settings.set_int('last-size', int(self.thickness_spinbtn.get_value()))
		self._settings.set_string('last-active-tool', self.active_tool_id)
		rgba = self.color_popover_l.color_widget.get_rgba()
		rgba = [str(rgba.red), str(rgba.green), str(rgba.blue), str(rgba.alpha)]
		self._settings.set_strv('last-left-rgba', rgba)
		rgba = self.color_popover_r.color_widget.get_rgba()
		rgba = [str(rgba.red), str(rgba.green), str(rgba.blue), str(rgba.alpha)]
		self._settings.set_strv('last-right-rgba', rgba)

		self._settings.set_boolean('maximized', self.is_maximized())
		return False

	# GENERAL PURPOSE METHODS

	def connect_signals(self):
		self.connect('delete-event', self.on_close)
		self.connect('configure-event', self.adapt_to_window_size)
		self.options_btn.connect('toggled', self.update_option_label)
		self._settings.connect('changed::show-labels', self.on_show_labels_setting_changed)

	def add_action_simple(self, action_name, callback):
		"""Convenient wrapper method adding a stateless action to the window. It
		will be named 'action_name' (string) and activating the action will
		trigger the method 'callback'."""
		action = Gio.SimpleAction.new(action_name, None)
		action.connect("activate", callback)
		self.add_action(action)

	def add_action_boolean(self, action_name, default, callback):
		"""Convenient wrapper method adding a stateful action to the window. It
		will be named 'action_name' (string), be created with the state 'default'
		(boolean), and activating the action will trigger the method 'callback'."""
		action = Gio.SimpleAction().new_stateful(action_name, None, \
			GLib.Variant.new_boolean(default))
		action.connect('change-state', callback)
		self.add_action(action)

	def add_action_enum(self, action_name, default, callback):
		"""Convenient wrapper method adding a stateful action to the window. It
		will be named 'action_name' (string), be created with the state 'default'
		(string), and changing the active target of the action will trigger the
		method 'callback'."""
		action = Gio.SimpleAction().new_stateful(action_name, \
			GLib.VariantType.new('s'), GLib.Variant.new_string(default))
		action.connect('change-state', callback)
		self.add_action(action)

	def add_all_win_actions(self):
		"""This doesn't add all window-wide GioActions, but only the GioActions
		which are here "by default", independently of any tool."""

		self.add_action_simple('main_menu', self.action_main_menu)
		self.add_action_simple('options_menu', self.action_options_menu)
		self.add_action_boolean('toggle_preview', False, self.action_toggle_preview)
		self.add_action_simple('properties', self.action_properties)
		self.add_action_boolean('show_labels', self._settings.get_boolean('show-labels'), \
			self.on_show_labels_changed)

		self.add_action_simple('go_up', self.action_go_up)
		self.add_action_simple('go_down', self.action_go_down)
		self.add_action_simple('go_left', self.action_go_left)
		self.add_action_simple('go_right', self.action_go_right)

		self.add_action_simple('new_tab', self.build_new_image)
		self.add_action_simple('close', self.action_close)
		self.add_action_simple('save', self.action_save)
		self.add_action_simple('open', self.action_open)
		self.add_action_simple('undo', self.action_undo)
		self.add_action_simple('redo', self.action_redo)
		self.add_action_simple('save_as', self.action_save_as)
		self.add_action_simple('export_as', self.action_export_as)
		self.add_action_simple('print', self.action_print)
		self.add_action_simple('import', self.action_import)
		self.add_action_simple('paste', self.action_paste)
		self.add_action_simple('select_all', self.action_select_all)
		self.add_action_simple('selection_export', self.action_selection_export) # XXX

		self.add_action_simple('back_to_former_tool', self.back_to_former_tool)
		self.add_action_simple('force_selection_tool', self.force_selection_tool)
		self.add_action_enum('active_tool', 'pencil', self.on_change_active_tool)
		self.add_action_simple('apply_selection_tool', self.action_apply_selection_tool)

		self.add_action_simple('main_color', self.action_main_color)
		self.add_action_simple('secondary_color', self.action_secondary_color)
		self.add_action_simple('exchange_color', self.action_exchange_color)

		self.app.add_action_boolean('use_editor', \
			self._settings.get_boolean('direct-color-edit'), self.action_use_editor)

		if self._settings.get_boolean('devel-only'):
			self.add_action_simple('restore_pixbuf', self.action_restore_pixbuf)
			self.add_action_simple('rebuild_from_histo', self.action_rebuild_from_histo)

	# WINDOW BARS

	def get_edition_status(self):
		return self.active_tool().get_edition_status()

	def set_picture_title(self):
		# if self.tools is None:
		# 	return
		fn = self.get_file_path()
		if fn is None:
			fn = _("Unsaved file")
		main_title = fn.split('/')[-1]
		if not self.get_active_image()._is_saved:
			main_title = '*' + main_title
		subtitle = self.get_edition_status()
		self.set_title(_("Drawing") + ' - ' + main_title + ' - ' + subtitle)
		if self.header_bar is not None:
			self.header_bar.set_title(main_title)
			self.header_bar.set_subtitle(subtitle)

	def get_auto_decorations(self):
		"""Return the decorations setting based on the XDG_CURRENT_DESKTOP
		environment variable."""
		desktop_env = os.getenv('XDG_CURRENT_DESKTOP', 'GNOME')
		if 'GNOME' in desktop_env:
			return 'csd'
		elif 'Pantheon' in desktop_env:
			return 'csd-eos'
		elif 'Unity' in desktop_env:
			return 'ssd-toolbar'
		elif 'Cinnamon' in desktop_env or 'MATE' in desktop_env or 'XFCE' in desktop_env:
			return 'ssd'
		else:
			return 'csd' # Use the GNOME layout if the desktop is unknown,
		# because i don't know how the env variable is on mobile.
		# Since hipsterwm users love "ricing", they'll be happy to edit
		# preferences themselves if they hate CSD.

	def set_ui_bars(self):
		"""Set the UI "bars" (headerbar, menubar, title, toolbar, whatever)
		according to the user's preference, which by default is 'auto'."""
		# Loading a whole file in a GtkBuilder just for this looked ridiculous,
		# so it's built from a string.
		builder = Gtk.Builder.new_from_string('''
<?xml version="1.0"?>
<interface>
  <menu id="tool-placeholder">
    <section>
      <item>
        <attribute name="action">none</attribute>
        <attribute name="label">''' + _("No options") + '''</attribute>
      </item>
    </section>
  </menu>
</interface>''', -1)
		self.placeholder_model = builder.get_object('tool-placeholder')

		# Remember the setting, so no need to restart this at each dialog.
		self.decorations = self._settings.get_string('decorations')
		if self.decorations == 'auto':
			self.decorations = self.get_auto_decorations()

		if self.decorations == 'csd':
			self.build_headerbar(False)
			self.set_titlebar(self.header_bar)
			self.set_show_menubar(False)
		elif self.decorations == 'csd-eos':
			self.build_headerbar(True)
			self.set_titlebar(self.header_bar)
			self.set_show_menubar(False)
		elif self.decorations == 'everything': # devel-only
			self.build_headerbar(False)
			self.set_titlebar(self.header_bar)
			self.set_show_menubar(True)
			self.build_toolbar()
		elif self.decorations == 'ssd-menubar':
			self.set_show_menubar(True)
		elif self.decorations == 'ssd-toolbar':
			self.build_toolbar()
			self.set_show_menubar(False)
		else: # self.decorations == 'ssd'
			self.build_toolbar()
			self.set_show_menubar(True)

		if self.app.is_beta():
			self.get_style_context().add_class('devel')

	def build_toolbar(self):
		builder = Gtk.Builder.new_from_resource('/com/github/maoschanz/Drawing/ui/toolbar.ui')
		toolbar = builder.get_object('toolbar')
		self.toolbar_box.add(toolbar)
		self.toolbar_box.show_all()

	def build_headerbar(self, is_eos):
		if is_eos:
			builder = Gtk.Builder.new_from_resource('/com/github/maoschanz/Drawing/ui/headerbar_eos.ui')
		else:
			builder = Gtk.Builder.new_from_resource('/com/github/maoschanz/Drawing/ui/headerbar.ui')
		self.header_bar = builder.get_object('header_bar')
		self.save_label = builder.get_object('save_label')
		self.save_icon = builder.get_object('save_icon')
		self.add_btn = builder.get_object('add_btn')
		self.main_menu_btn = builder.get_object('main_menu_btn')

		builder.add_from_resource('/com/github/maoschanz/Drawing/ui/win-menus.ui')
		short_main_menu = builder.get_object('short-window-menu')
		self.short_menu_popover = Gtk.Popover.new_from_model(self.main_menu_btn, short_main_menu)
		long_main_menu = builder.get_object('long-window-menu')
		self.long_menu_popover = Gtk.Popover.new_from_model(self.main_menu_btn, long_main_menu)

		if not is_eos:
			add_menu = builder.get_object('add-menu')
			add_popover = Gtk.Popover.new_from_model(self.add_btn, add_menu)
			self.add_btn.set_popover(add_popover)

	def action_main_menu(self, *args):
		if self.main_menu_btn is not None:
			self.main_menu_btn.set_active(not self.main_menu_btn.get_active())

	def action_options_menu(self, *args): # TODO disable if custom panel
		self.options_btn.set_active(not self.options_btn.get_active())

	def adapt_to_window_size(self, *args):
		"""Adapts the headerbar (if any) and the default bottom panel to the new
		window size. If the current bottom panel isn't the default one, this will
		call the tool method applying the new size to the tool panel."""
		if self.header_bar is not None:
			widgets_width = self.save_label.get_allocated_width() \
				+ self.save_icon.get_allocated_width() \
				+ self.add_btn.get_allocated_width()
			limit = 3 * widgets_width # 100% arbitrary
			if self.header_bar.get_allocated_width() > limit:
				self.save_label.set_visible(True)
				self.save_icon.set_visible(False)
				self.add_btn.set_visible(True)
				self.main_menu_btn.set_popover(self.short_menu_popover)
			else:
				self.save_label.set_visible(False)
				self.save_icon.set_visible(True)
				self.add_btn.set_visible(False)
				self.main_menu_btn.set_popover(self.long_menu_popover)

		if self.active_tool().implements_panel:
			self.active_tool().adapt_to_window_size()
		else:
			available_width = self.bottom_panel_box.get_allocated_width()
			if self.minimap_label.get_visible():
				self.needed_width_for_long = self.color_box.get_allocated_width() + \
					self.thickness_spinbtn.get_allocated_width() + \
					self.options_long_box.get_preferred_width()[0] + \
					self.minimap_label.get_preferred_width()[0]
			if self.needed_width_for_long > 0.7 * available_width:
				self.compact_preview_btn(True)
				self.compact_options_btn(True)
			else:
				self.compact_options_btn(False)
				self.compact_preview_btn(False)

	def compact_options_btn(self, state):
		self.options_short_box.set_visible(state)
		self.options_long_box.set_visible(not state)

	def compact_preview_btn(self, state):
		self.minimap_label.set_visible(not state)
		self.minimap_arrow.set_visible(not state)
		self.minimap_icon.set_visible(state)

	def prompt_message(self, show, label):
		"""Update the content and the visibility of the info bar."""
		self.info_bar.set_visible(show)
		if show:
			self.info_label.set_label(label)
		if self._settings.get_boolean('devel-only'):
			print('Drawing: ' + label)

	def update_tabs_visibility(self):
		self.notebook.set_show_tabs(self.notebook.get_n_pages() > 1)

	# TOOLS PANEL

	def build_tool_rows(self):
		"""Adds each tool's button to the side panel, or to the selection's
		bottom panel."""
		group = None
		for tool_id in self.tools:
			if group is None:
				group = self.tools[tool_id].row
			else:
				self.tools[tool_id].row.join_group(group)
			self.tools_panel.add(self.tools[tool_id].row)
			if self.tools[tool_id].is_hidden:
				self.get_selection_tool().add_subtool(self.tools[tool_id])
		self.on_show_labels_setting_changed()

	def set_tools_labels_visibility(self, visible):
		if visible:
			for label in self.tools:
				self.tools[label].label_widget.set_visible(True)
		else:
			for label in self.tools:
				self.tools[label].label_widget.set_visible(False)

	def on_show_labels_setting_changed(self, *args): # TODO actions bound to settings are a thing
		self.set_tools_labels_visibility(self._settings.get_boolean('show-labels'))

	def on_show_labels_changed(self, *args):
		show_labels = not args[0].get_state()
		self._settings.set_boolean('show-labels', show_labels)
		args[0].set_state(GLib.Variant.new_boolean(show_labels))

	# TOOLS

	def on_change_active_tool(self, *args):
		state_as_string = args[1].get_string()
		if state_as_string == args[0].get_state().get_string():
			return
		elif self.tools[state_as_string].row.get_active():
			args[0].set_state(GLib.Variant.new_string(state_as_string))
			self.enable_tool(state_as_string, True)
		else:
			self.tools[state_as_string].row.set_active(True)

	def enable_tool(self, new_tool_id, should_give_back_control):
		former_tool_id_2 = self.former_tool_id
		self.former_tool_id = self.active_tool_id
		if should_give_back_control:
			self.former_tool().give_back_control()
		self.former_tool().on_tool_unselected()
		self.get_active_image().queue_draw()
		self.active_tool_id = new_tool_id
		self.update_bottom_panel()
		self.active_tool().on_tool_selected()
		self.set_picture_title()
		if self.former_tool().implements_panel:
			self.former_tool_id = former_tool_id_2

	def update_bottom_panel(self):
		"""Show the correct bottom panel, with the correct tool options menu."""
		self.build_options_menu()
		if self.former_tool_id is not self.active_tool_id:
			self.former_tool().show_panel(False)
		self.active_tool().show_panel(True)
		self.update_thickness_spinbtn_state()
		self.adapt_to_window_size()

	def active_tool(self):
		return self.tools[self.active_tool_id]

	def former_tool(self):
		return self.tools[self.former_tool_id]

	def back_to_former_tool(self, *args):
		if self.hijacker_id is not None:
			self.hijack_end()
		else:
			self.tools[self.former_tool_id].row.set_active(True)

	def hijack_begin(self, hijacker_id, target_id):
		self.lookup_action('active_tool').set_enabled(False)
		self.hijacker_id = hijacker_id
		self.enable_tool(target_id, False)

	def hijack_end(self):
		if self.hijacker_id is not None:
			self.enable_tool(self.hijacker_id, False)
		self.hijacker_id = None
		self.lookup_action('active_tool').set_enabled(True)

	# FILE MANAGEMENT

	def action_properties(self, *args):
		self.get_active_image().edit_properties()

	def get_active_image(self):
		return self.image_list[self.notebook.get_current_page()]

	def get_file_path(self):
		return self.get_active_image().get_file_path()

	def action_open(self, *args):
		gfile = self.file_chooser_open()
		if gfile is None:
			return
		else:
			self.prompt_message(True, _("Loading %s") % \
				(gfile.get_path().split('/')[-1]))
		if self.get_active_image()._is_saved:
			self.try_load_file(gfile)
		else:
			dialog = Gtk.MessageDialog(modal=True, title=_("Unsaved changes"), \
				transient_for=self)
			dialog.add_button(_("New tab"), Gtk.ResponseType.OK)
			dialog.add_button(_("New window"), Gtk.ResponseType.ACCEPT)
			dialog.add_button(_("Discard changes"), Gtk.ResponseType.APPLY)
			label1 = Gtk.Label( label=( _("There are unsaved modifications to %s.") % \
				self.get_active_image().get_filename_for_display() ), wrap=True)
			dialog.get_message_area().add(label1)
			label2 = Gtk.Label( \
				label=(_("Where do you want to open %s?") %  \
				(gfile.get_path().split('/')[-1])), wrap=True) # FIXME
			dialog.get_message_area().add(label2)
			dialog.show_all()
			result = dialog.run()
			dialog.destroy()
			if result == Gtk.ResponseType.OK:
				self.build_new_tab(gfile)
				self.prompt_message(False, 'load the file in a new tab')
			elif result == Gtk.ResponseType.APPLY:
				self.try_load_file(gfile)
				self.prompt_message(False, 'load the file in the same tab')
			elif result == Gtk.ResponseType.ACCEPT:
				self.app.open_window_with_file(gfile)
				self.prompt_message(False, 'load the file in a new window')

	def file_chooser_open(self, *args):
		"""Opens an "open" file chooser dialog, and return a GioFile or None."""
		gfile = None
		file_chooser = Gtk.FileChooserNative.new(_("Open a picture"), self,
			Gtk.FileChooserAction.OPEN,
			_("Open"),
			_("Cancel"))
		self.add_filechooser_filters(file_chooser)

		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			gfile = file_chooser.get_file()
		file_chooser.destroy()
		return gfile

	def action_save(self, *args):
		fn = self.get_file_path()
		if fn is None:
			gfile = self.file_chooser_save()
			if gfile is not None:
				self.get_active_image().gfile = gfile
		fn = self.get_file_path()
		if fn is not None:
			utilities_save_pixbuf_at(self.get_active_image().main_pixbuf, fn)
		self.get_active_image().post_save()
		self.set_picture_title()

	def action_save_as(self, *args):
		gfile = self.file_chooser_save()
		if gfile is not None:
			self.get_active_image().gfile = gfile
		self.action_save()

	def try_load_file(self, gfile):
		if gfile is not None:
			self.get_active_image().try_load_file(gfile)
		self.set_picture_title()
		self.prompt_message(False, 'file successfully loaded')

	def confirm_save_modifs(self):
		"""Return True if the image can be closed/overwritten (whether it's saved
		or not), or False if the image can't be closed/overwritten."""
		if self.get_active_image()._is_saved:
			return True
		fn = self.get_file_path()
		if fn is None:
			unsaved_file_name = _("Untitled") + '.png'
		else:
			unsaved_file_name = fn.split('/')[-1]
		dialog = Gtk.MessageDialog(modal=True, title=_("Unsaved changes"), \
			transient_for=self)
		dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
		dialog.add_button(_("Discard"), Gtk.ResponseType.NO)
		dialog.add_button(_("Save"), Gtk.ResponseType.APPLY)
		label1 = Gtk.Label( label=( _("There are unsaved modifications to %s.") % \
			self.get_active_image().get_filename_for_display() ), wrap=True)
		dialog.get_message_area().add(label1)
		dialog.show_all()
		dialog.set_size_request(0, 0)
		result = dialog.run()
		if result == Gtk.ResponseType.APPLY:
			dialog.destroy()
			self.action_save()
			return True
		elif result == Gtk.ResponseType.NO:
			dialog.destroy()
			return True
		else:
			dialog.destroy()
			return False

	def add_filechooser_filters(self, dialog):
		"""Add file filters for images to file chooser dialogs."""
		allPictures = Gtk.FileFilter()
		allPictures.set_name(_("All pictures"))
		allPictures.add_mime_type('image/png')
		allPictures.add_mime_type('image/jpeg')
		allPictures.add_mime_type('image/bmp')

		pngPictures = Gtk.FileFilter()
		pngPictures.set_name(_("PNG images"))
		pngPictures.add_mime_type('image/png')

		jpegPictures = Gtk.FileFilter()
		jpegPictures.set_name(_("JPEG images"))
		jpegPictures.add_mime_type('image/jpeg')

		bmpPictures = Gtk.FileFilter()
		bmpPictures.set_name(_("BMP images"))
		bmpPictures.add_mime_type('image/bmp')

		dialog.add_filter(allPictures)
		dialog.add_filter(pngPictures)
		dialog.add_filter(jpegPictures)
		dialog.add_filter(bmpPictures)

	def file_chooser_save(self):
		"""Opens an "save" file chooser dialog, and return a GioFile or None."""
		gfile = None
		file_chooser = Gtk.FileChooserNative.new(_("Save picture as…"), self,
			Gtk.FileChooserAction.SAVE,
			_("Save"),
			_("Cancel"))
		self.add_filechooser_filters(file_chooser)
		default_file_name = str(_("Untitled") + '.png')
		file_chooser.set_current_name(default_file_name)

		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			gfile = file_chooser.get_file()
		file_chooser.destroy()
		return gfile

	def action_export_as(self, *args):
		gfile = self.file_chooser_save()
		if gfile is not None:
			utilities_save_pixbuf_at(self.main_pixbuf, gfile.get_path())

	def action_print(self, *args):
		self.get_active_image().print_image()

	def action_select_all(self, *args):
		self.force_selection_tool()
		self.get_active_image().image_select_all()
		self.get_selection_tool().selection_select_all()

	def action_paste(self, *args):
		self.force_selection_tool()
		self.get_selection_tool().selection_paste()

	def action_import(self, *args):
		file_chooser = Gtk.FileChooserNative.new(_("Import a picture"), self,
			Gtk.FileChooserAction.OPEN,
			_("Import"),
			_("Cancel"))
		self.add_filechooser_filters(file_chooser)
		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			self.force_selection_tool()
			fn = file_chooser.get_filename()
			self.get_active_image().set_selection_pixbuf(GdkPixbuf.Pixbuf.new_from_file(fn))
			self.get_selection_tool().selection_import()
		file_chooser.destroy()

	def action_selection_export(self, *args):
		gfile = self.file_chooser_save()
		if gfile is not None:
			utilities_save_pixbuf_at(self.get_active_image().get_selection_pixbuf(), gfile.get_path())

	def get_selection_tool(self):
		return self.tools['select']

	def force_selection_tool(self, *args):
		if self.hijacker_id is not None:
			self.hijack_end()
		else:
			self.get_selection_tool().row.set_active(True)

	def action_apply_selection_tool(self, *args):
		self.active_tool().on_apply()

	def tool_needs_selection(self):
		return ( self.active_tool() is self.get_selection_tool() )

	# HISTORY MANAGEMENT

	def action_undo(self, *args):
		self.get_active_image().try_undo()
		self.action_rebuild_from_histo()

	def action_redo(self, *args):
		self.get_active_image().try_redo()
		self.action_rebuild_from_histo()

	def operation_is_ongoing(self): # TODO
		# if self.active_tool() is self.get_selection_tool():
		# 	is_ongoing = self.active_tool().selection_has_been_used
		# else:
		# 	is_ongoing = self.active_tool().has_ongoing_operation
		# return is_ongoing
		return False

	def action_restore_pixbuf(self, *args):
		self.get_active_image().use_stable_pixbuf()
		self.get_active_image().queue_draw()

	def action_rebuild_from_histo(self, *args):
		self.get_active_image().restore_first_pixbuf()
		h = self.get_active_image().undo_history.copy()
		self.get_active_image().undo_history = []
		for op in h:
			self.tools[op['tool_id']].apply_operation(op)
		self.get_active_image().queue_draw()
		self.get_active_image().update_history_sensitivity(True)

	# COLORS

	def build_color_buttons(self):
		"""Initialize the 2 color buttons and popovers with the 2 previously
		memorized RGBA values."""
		right_rgba = self._settings.get_strv('last-right-rgba')
		r = float(right_rgba[0])
		g = float(right_rgba[1])
		b = float(right_rgba[2])
		a = float(right_rgba[3])
		right_rgba = Gdk.RGBA(red=r, green=g, blue=b, alpha=a)
		left_rgba = self._settings.get_strv('last-left-rgba')
		r = float(left_rgba[0])
		g = float(left_rgba[1])
		b = float(left_rgba[2])
		a = float(left_rgba[3])
		left_rgba = Gdk.RGBA(red=r, green=g, blue=b, alpha=a)
		self.color_popover_r = DrawingColorPopover(self.color_menu_btn_r, self.r_btn_image, right_rgba)
		self.color_popover_l = DrawingColorPopover(self.color_menu_btn_l, self.l_btn_image, left_rgba)

	def action_use_editor(self, *args):
		use_editor = not args[0].get_state()
		self._settings.set_boolean('direct-color-edit', use_editor)
		args[0].set_state(GLib.Variant.new_boolean(use_editor))
		self.set_palette_setting()

	def set_palette_setting(self, *args):
		show_editor = self._settings.get_boolean('direct-color-edit')
		self.color_popover_r.setting_changed(show_editor)
		self.color_popover_l.setting_changed(show_editor)

	def action_main_color(self, *args):
		self.color_menu_btn_l.activate()

	def action_secondary_color(self, *args):
		self.color_menu_btn_r.activate()

	def action_exchange_color(self, *args):
		left_c = self.color_popover_l.color_widget.get_rgba()
		self.color_popover_l.color_widget.set_rgba(self.color_popover_r.color_widget.get_rgba())
		self.color_popover_r.color_widget.set_rgba(left_c)

	# TOOLS OPTIONS

	def update_thickness_spinbtn_state(self):
		self.thickness_spinbtn.set_sensitive(self.active_tool().use_size)

	def build_options_menu(self):
		widget = self.active_tool().get_options_widget()
		model = self.active_tool().get_options_model()
		if model is None:
			self.app.get_menubar().remove(5)
			self.app.get_menubar().insert_submenu(5, _("_Options"), self.placeholder_model)
		else:
			self.app.get_menubar().remove(5)
			self.app.get_menubar().insert_submenu(5, _("_Options"), model)
		if widget is not None:
			self.options_btn.set_popover(widget)
		elif model is not None:
			self.options_btn.set_menu_model(model)
		else:
			self.options_btn.set_popover(None)
		self.update_option_label()

	def update_option_label(self, *args):
		self.options_label.set_label(self.active_tool().get_options_label())

	# PREVIEW & NAVIGATION

	def action_toggle_preview(self, *args):
		"""Action callback, showing or hiding the "minimap" preview popover."""
		preview_visible = not args[0].get_state()
		if preview_visible:
			self.minimap.popup()
			self.minimap.update_minimap()
		else:
			self.minimap.popdown()
		args[0].set_state(GLib.Variant.new_boolean(preview_visible))

	def action_go_up(self, *args):
		self.get_active_image().add_deltas(0, -1, 100)

	def action_go_down(self, *args):
		self.get_active_image().add_deltas(0, 1, 100)

	def action_go_left(self, *args):
		self.get_active_image().add_deltas(-1, 0, 100)

	def action_go_right(self, *args):
		self.get_active_image().add_deltas(1, 0, 100)

