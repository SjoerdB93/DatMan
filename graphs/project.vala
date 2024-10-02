// SPDX-License-Identifier: GPL-3.0-or-later
using Adw;
using Gtk;

namespace Graphs {
    namespace Project {

        public FileFilter get_project_file_filter () {
            return Tools.create_file_filter (
                C_("file-filter", "Graphs Project File"), "graphs"
            );
        }

        private void _save (Window window) {
            window.data.save ();
            window.add_toast_string_with_file (
                _("Saved Project"), window.data.file
            );
        }

        private ListModel get_project_file_filters () {
            return Tools.create_file_filters (false, get_project_file_filter ());
        }

        public async bool save (Window window, bool require_dialog) {
            if (window.data.file != null && !require_dialog) {
                _save (window);
                return true;
            }
            var dialog = new FileDialog ();
            dialog.set_filters (get_project_file_filters ());
            dialog.set_initial_name (_("Project") + ".graphs");
            try {
                window.data.file = yield dialog.save (window, null);
                _save (window);
                return true;
            } catch {
                return false;
            }
        }

        private void _pick_and_load (Window window) {
            var dialog = new FileDialog ();
            dialog.set_filters (get_project_file_filters ());
            dialog.open.begin (window, null, (d, response) => {
                try {
                    window.data.file = dialog.open.end (response);
                    window.data.load ();
                } catch {}
            });
        }

        public void open (Window window) {
            if (!window.data.unsaved) {
                _pick_and_load (window);
                return;
            }
            var dialog = Tools.build_dialog ("save_changes") as Adw.AlertDialog;
            dialog.response.connect ((d, response) => {
                switch (response) {
                    case "discard_close": {
                        _pick_and_load (window);
                        break;
                    }
                    case "save_close": {
                        save.begin (window, false, (o, result) => {
                            save.end (result);
                            _pick_and_load (window);
                        });
                        break;
                    }
                }
            });
            dialog.present (window);
        }

        public void @new (Window window) {
            if (!window.data.unsaved) {
                window.data.reset ();
                return;
            }
            var dialog = Tools.build_dialog ("save_changes") as Adw.AlertDialog;
            dialog.response.connect ((d, response) => {
                switch (response) {
                    case "discard_close": {
                        window.data.reset ();
                        break;
                    }
                    case "save_close": {
                        save.begin (window, false, (o, result) => {
                            save.end (result);
                            window.data.reset ();
                        });
                        break;
                    }
                }
            });
            dialog.present (window);
        }
    }
}
