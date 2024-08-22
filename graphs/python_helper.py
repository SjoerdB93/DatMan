# SPDX-License-Identifier: GPL-3.0-or-later
"""Python Helper - Python part."""
import logging
from gettext import gettext as _

from gi.repository import Gio, Graphs

from graphs import (
    curve_fitting,
    edit_item,
    export_items,
    file_import,
    utilities,
)
from graphs.item import DataItem
from graphs.style_editor import StyleEditor

import numexpr

import numpy

_REQUEST_NAMES = (
    "python_method_request",
    "edit_item_dialog_request",
    "curve_fitting_dialog_request",
    "evaluate_string_request",
    "import_from_files_request",
    "export_items_request",
    "add_equation_request",
    "open_style_editor_request",
)


class PythonHelper(Graphs.PythonHelper):
    """Python helper for python only calls."""

    def __init__(self, application: Graphs.Application):
        super().__init__(application=application)

        for request_name in _REQUEST_NAMES:
            self.connect(
                request_name,
                getattr(self, "_on_" + request_name),
            )

    @staticmethod
    def _on_python_method_request(self, obj, method: str) -> None:
        getattr(obj, method)()

    @staticmethod
    def _on_edit_item_dialog_request(self, item) -> None:
        return edit_item.EditItemDialog(self.props.application, item)

    @staticmethod
    def _on_curve_fitting_dialog_request(self, item) -> None:
        return curve_fitting.CurveFittingDialog(self.props.application, item)

    @staticmethod
    def _on_evaluate_string_request(self, string: str) -> None:
        value = utilities.string_to_float(string)
        if value is None:
            return False
        self.set_evaluate_string_helper(value)
        return True

    @staticmethod
    def _on_import_from_files_request(
        self,
        files: list[Gio.File],
        _n_files: int,
    ) -> None:
        return file_import.import_from_files(self.props.application, files)

    @staticmethod
    def _on_export_items_request(
        self,
        mode: str,
        file: Gio.File,
        items: list[Graphs.Item],
        _n_items: int,
    ) -> None:
        return export_items.export_items(mode, file, items)

    @staticmethod
    def _on_add_equation_request(self, name: str) -> str:
        settings = self.props.application.get_settings_child("add-equation")
        try:
            x_start = utilities.string_to_float(settings.get_string("x-start"))
            x_stop = utilities.string_to_float(settings.get_string("x-stop"))
            step_size = utilities.string_to_float(
                settings.get_string("step-size"),
            )
            datapoints = int(abs(x_start - x_stop) / step_size) + 1
            xdata = numpy.ndarray.tolist(
                numpy.linspace(x_start, x_stop, datapoints),
            )
            equation = utilities.preprocess(settings.get_string("equation"))
            ydata = numpy.ndarray.tolist(
                numexpr.evaluate(equation + " + x*0", local_dict={"x": xdata}),
            )
            if name == "":
                name = f"Y = {settings.get_string('equation')}"
            style_manager = self.props.application.get_figure_style_manager()
            self.props.application.get_data().add_items(
                [
                    DataItem.new(
                        style_manager.get_selected_style_params(),
                        xdata,
                        ydata,
                        name=name,
                    ),
                ],
                style_manager,
            )
            return ""
        except ValueError as error:
            return str(error)
        except (NameError, SyntaxError, TypeError, KeyError) as exception:
            message = _("{error} - Unable to add data from equation")
            msg = message.format(error=exception.__class__.__name__)
            logging.exception(msg)
            return msg

    @staticmethod
    def _on_open_style_editor_request(self, file: Gio.File) -> None:
        window = StyleEditor(self.props.application)
        window.load_style(file)
        window.present()
