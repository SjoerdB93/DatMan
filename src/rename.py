# SPDX-License-Identifier: GPL-3.0-or-later
from gettext import gettext as _

from gi.repository import Adw, Gtk

from graphs import graphs


@Gtk.Template(resource_path="/se/sjoerd/Graphs/ui/rename_window.ui")
class RenameWindow(Adw.Window):
    __gtype_name__ = "RenameWindow"
    text_entry = Gtk.Template.Child()
    preferencegroup = Gtk.Template.Child()

    def __init__(self, application, item):
        super().__init__(application=application)
        self.item = item
        title = _("Rename Label")
        group_title = _("Change Label")
        group_description = \
            _("Here you can change the label of the selected axis.")
        text = self.item.get_text()
        if self.item == self.props.application.canvas.title:
            title = _("Rename Title")
            group_title = _("Change Title")
            group_description = \
                _("Here you can change the title of the plot.")
            text = self.props.application.plot_settings.title
        self.set_title(title)
        self.preferencegroup.set_title(group_title)
        self.preferencegroup.set_description(group_description)
        self.text_entry.set_text(text)
        self.set_transient_for(self.props.application.main_window)
        self.present()

    @Gtk.Template.Callback()
    def on_accept(self, _widget):
        text = self.text_entry.get_text()
        if self.item == self.props.application.canvas.top_label:
            self.props.application.plot_settings.top_label = text
        if self.item == self.props.application.canvas.left_label:
            self.props.application.plot_settings.ylabel = text
        if self.item == self.props.application.canvas.bottom_label:
            self.props.application.plot_settings.xlabel = text
        if self.item == self.props.application.canvas.right_label:
            self.props.application.plot_settings.right_label = text
        if self.item == self.props.application.canvas.title:
            self.props.application.plot_settings.title = text
        graphs.refresh(self.props.application)
        self.destroy()
