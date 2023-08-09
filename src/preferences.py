# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from gettext import gettext as _

from gi.repository import Adw, GObject, Gio, Gtk

from graphs import file_io, graphs, plot_styles, ui, utilities


MIGRATION_KEYS = {
    # new: old
    "other_handle_duplicates": "handle_duplicates",
    "other_hide_unselected": "hide_unselected",
}


def _validate(config: dict, template: dict):
    """
    Validates a given dictionary against a template, such that they
    remain compatible with updated versions of Graphs. If the key in the
    dictionary is not present in the template due to an update, the key will
    be updated using MIGRATION_KEYS.

    If the template or validated key does not match with the MIGRATION_KEYS,
    the template keys and their associated values will be used instead for
    the validated dictionary.

    Args:
        config: Dictionary to be validated
        template: Template dictionary to which the config is validated against
    Returns:
        dict: Validated dictionary
    """
    return {key: config[key if key in config else MIGRATION_KEYS[key]]
            if key in config
            or (key in MIGRATION_KEYS and MIGRATION_KEYS[key] in config)
            else value for key, value in template.items()}


class Preferences(dict):
    def __init__(self):
        config_dir = utilities.get_config_directory()
        if not config_dir.query_exists(None):
            config_dir.make_directory_with_parents(None)
        config_file = config_dir.get_child_for_display_name("config.json")
        import_file = config_dir.get_child_for_display_name("import.json")
        template_config_file = Gio.File.new_for_uri(
            "resource:///se/sjoerd/Graphs/config.json")
        template_import_file = Gio.File.new_for_uri(
            "resource:///se/sjoerd/Graphs/import.json")
        if not config_file.query_exists(None):
            template_config_file.copy(
                config_file, Gio.FileCopyFlags(1), None, None, None)
            logging.info(_("New configuration file created"))
        if not import_file.query_exists(None):
            template_import_file.copy(
                import_file, Gio.FileCopyFlags(1), None, None, None)
            logging.info(_("New Import Settings file created"))

        super().update(_validate(
            file_io.parse_json(config_file),
            file_io.parse_json(template_config_file)))

        import_params_template = file_io.parse_json(template_import_file)
        self["import_params"] = _validate({
            key: _validate(item, import_params_template[key])
            for key, item in file_io.parse_json(import_file).items()
        }, import_params_template)

    def update(self, values: dict):
        super().update(values)
        self.save()

    def update_modes(self, values: dict):
        for mode, params in values.items():
            self["import_params"][mode].update(params)
        self.save()

    def save(self):
        config_dir = utilities.get_config_directory()
        config = self.copy()
        file_io.write_json(
            config_dir.get_child_for_display_name("import.json"),
            config["import_params"])
        del config["import_params"]
        file_io.write_json(
            config_dir.get_child_for_display_name("config.json"),
            config)


@Gtk.Template(resource_path="/se/sjoerd/Graphs/ui/preferences.ui")
class PreferencesWindow(Adw.PreferencesWindow):
    __gtype_name__ = "PreferencesWindow"
    general_center = Gtk.Template.Child()
    general_handle_duplicates = Gtk.Template.Child()
    general_hide_unselected = Gtk.Template.Child()
    general_override_item_properties = Gtk.Template.Child()
    figure_title = Gtk.Template.Child()
    figure_bottom_label = Gtk.Template.Child()
    figure_left_label = Gtk.Template.Child()
    figure_top_label = Gtk.Template.Child()
    figure_right_label = Gtk.Template.Child()
    figure_bottom_scale = Gtk.Template.Child()
    figure_left_scale = Gtk.Template.Child()
    figure_top_scale = Gtk.Template.Child()
    figure_right_scale = Gtk.Template.Child()
    figure_x_position = Gtk.Template.Child()
    figure_y_position = Gtk.Template.Child()
    figure_legend = Gtk.Template.Child()
    figure_legend_position = Gtk.Template.Child()
    figure_use_custom_style = Gtk.Template.Child()
    figure_custom_style = Gtk.Template.Child()

    styles = GObject.Property(type=object)

    def __init__(self, application):
        super().__init__(
            application=application, transient_for=application.main_window,
            styles=sorted(list(
                plot_styles.get_user_styles(application).keys())),
        )

        self.figure_custom_style.set_model(Gtk.StringList.new(self.styles))
        settings = self.props.application.settings
        ui.bind_values_to_settings(
            settings.get_child("figure"), self, prefix="figure_",
            ignorelist=["custom-style"])
        ui.bind_values_to_settings(
            settings.get_child("general"), self, prefix="general_")
        self.figure_custom_style.set_selected(self.styles.index(
            settings.get_child("figure").get_string("custom-style")))
        self.present()

    @Gtk.Template.Callback()
    def on_close(self, _):
        self.props.application.settings.get_child("figure").set_string(
            "custom-style",
            self.figure_custom_style.get_selected_item().get_string())
        graphs.refresh(self.props.application)
