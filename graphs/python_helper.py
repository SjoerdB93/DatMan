# SPDX-License-Identifier: GPL-3.0-or-later
"""Python Helper - Python part."""
from gi.repository import Graphs

from graphs import figure_settings

_REQUEST_NAMES = (
    "figure_settings_dialog_request",
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
    def _on_figure_settings_dialog_request(self):
        return figure_settings.FigureSettingsDialog(self.props.application)
