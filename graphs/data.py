# SPDX-License-Identifier: GPL-3.0-or-later
"""Data management module."""
import copy
import logging
import math
import os
from gettext import gettext as _
from urllib.parse import unquote, urlparse

from gi.repository import Graphs

from graphs import item, misc, project, style_io, utilities

from matplotlib import RcParams

import numpy

_FIGURE_SETTINGS_HISTORY_IGNORELIST = misc.LIMITS + [
    "min_selected",
    "max_selected",
]


class Data(Graphs.Data):
    """Class for managing data."""

    __gtype_name__ = "GraphsPythonData"

    def __init__(self, application: Graphs.Application):
        super().__init__(application=application)
        self.connect("python_method_request", self._on_python_method_request)
        self._selected_style_params = None
        self.setup()
        limits = self.props.figure_settings.get_limits()
        self._history_states = [([], limits)]
        self._history_pos = -1
        self._view_history_states = [limits]
        self._view_history_pos = -1
        self._set_data_copy()
        self.props.figure_settings.connect(
            "notify",
            self._on_figure_settings_change,
        )
        self.connect("notify::unsaved", self._on_unsaved_change)
        self._update_used_positions()
        self._on_unsaved_change(None, None)
        self.connect("item_changed", self._on_item_changed)
        self.connect("delete_request", self._on_delete_request)
        self.connect("position_changed", self._on_position_changed)

    @staticmethod
    def _on_python_method_request(self, method: str) -> None:
        getattr(self, method)()

    def _on_unsaved_change(self, _a, _b) -> None:
        if self.props.file is None:
            title = _("Untitled Project")
            path = _("Draft")
        else:
            title = Graphs.tools_get_filename(self.props.file)
            uri_parse = urlparse(self.props.file.get_uri())
            filepath = os.path.dirname(
                os.path.join(uri_parse.netloc, unquote(uri_parse.path)),
            )
            if filepath.startswith("/var"):
                # Fix for rpm-ostree distros, where home is placed in /var/home
                filepath = filepath.replace("/var", "", 1)
            path = filepath.replace(os.path.expanduser("~"), "~")
            if path.startswith(f"/run/user/{os.getuid()}/doc/"):
                path = _("Document Portal")
        if self.props.unsaved:
            title = "• " + title
        self.props.project_name = title
        self.props.project_path = path

    def __len__(self) -> int:
        """Magic alias for `get_n_items()`."""
        return self.get_n_items()

    def __iter__(self):
        """Iterate over items."""
        return iter(self.get_items())

    def __getitem__(self, getter: str | int):
        """Magic alias for retrieving items."""
        if isinstance(getter, str):
            return self.get_for_uuid(getter)
        return self.get_item(getter)

    def get_old_selected_style_params(self) -> RcParams:
        """Get the old selected style properties."""
        return self._old_style_params

    def get_selected_style_params(self) -> RcParams:
        """Get the selected style properties."""
        return self._selected_style_params

    def _update_selected_style(self) -> None:
        figure_settings = self.props.figure_settings
        style_manager = self.props.application.get_figure_style_manager()
        error_msg = None
        if figure_settings.get_use_custom_style():
            stylename = figure_settings.get_custom_style()
            for style in self.props.style_selection_model.get_model():
                if stylename == style.get_name():
                    try:
                        validate = None
                        if style.get_mutable():
                            validate = style_manager.get_system_style_params()
                        self._old_style_params = self._selected_style_params
                        self._selected_style_params = style_io.parse(
                            style.get_file(),
                            validate,
                        )[0]
                        return
                    except (ValueError, SyntaxError, AttributeError):
                        error_msg = _(
                            f"Could not parse {stylename}, loading "
                            "system preferred style",
                        ).format(stylename=stylename)
                    break
            error_msg = _(
                f"Plot style {stylename} does not exist "
                "loading system preferred",
            ).format(stylename=stylename)
        if error_msg is not None:
            figure_settings.set_use_custom_style(False)
            logging.warning(error_msg)
        self._old_style_params = self._selected_style_params
        self._selected_style_params = style_manager.get_system_style_params()

    @staticmethod
    def _on_position_changed(self, index1: int, index2: int) -> None:
        """Change item position of index2 to that of index1."""
        self._current_batch.append((3, (index2, index1)))

    def add_items(self, items: misc.ItemList) -> None:
        """
        Add items to be managed.

        Respects settings in regards to handling duplicate names.
        New Items with a x- or y-label change the figures current labels if
        they are still the default. If they are already modified and do not
        match the items label, they get moved to another axis.
        """
        figure_settings = self.get_figure_settings()
        settings = self.get_application().get_settings_child("figure")
        color_cycle = self._selected_style_params["axes.prop_cycle"].by_key(
        )["color"]
        used_colors = []

        def _append_used_color(color):
            used_colors.append(color)
            if len(set(used_colors)) == len(color_cycle):
                for color in color_cycle:
                    used_colors.remove(color)

        def _is_default(prop):
            return figure_settings.get_property(prop) == \
                settings.get_string(prop)

        for item_ in self:
            color = item_.get_color()
            if color in color_cycle:
                _append_used_color(color)
        used_names = set(self.get_names())
        prev_size = self.get_n_items()
        for new_item in items:
            item_name = new_item.get_name()
            if item_name in used_names:
                new_item.set_name(
                    Graphs.tools_get_duplicate_string(
                        item_name,
                        list(used_names),
                    ),
                )
            used_names.add(new_item.get_name())
            xlabel = new_item.get_xlabel()
            if xlabel:
                original_position = new_item.get_xposition()
                if original_position == 0:
                    if _is_default("bottom-label") or self.is_empty():
                        figure_settings.set_bottom_label(xlabel)
                    elif xlabel != figure_settings.get_bottom_label():
                        new_item.set_xposition(1)
                if new_item.get_xposition() == 1:
                    if _is_default("top-label"):
                        figure_settings.set_top_label(xlabel)
                    elif xlabel != figure_settings.get_top_label():
                        new_item.set_xposition(original_position)
            ylabel = new_item.get_ylabel()
            if ylabel:
                original_position = new_item.get_yposition()
                if original_position == 0:
                    if _is_default("left-label") or self.is_empty():
                        figure_settings.set_left_label(ylabel)
                    elif ylabel != figure_settings.get_left_label():
                        new_item.set_yposition(1)
                if new_item.get_yposition() == 1:
                    if _is_default("right-label"):
                        figure_settings.set_right_label(ylabel)
                    elif ylabel != figure_settings.get_right_label():
                        new_item.set_yposition(original_position)
            if new_item.get_color() == "":
                for color in color_cycle:
                    if color not in used_colors:
                        _append_used_color(color)
                        new_item.set_color(color)
                        break

            self._add_item(new_item, -1, False)
            change = (1, copy.deepcopy(new_item.to_dict()))
            self._current_batch.append(change)
        self.emit("items_changed", prev_size, 0, len(items))
        self._optimize_limits()
        self._add_history_state()

    @staticmethod
    def _on_delete_request(self, items: misc.ItemList, _num):
        """Delete specified items."""
        settings = self.get_figure_settings()
        for item_ in items:
            self._current_batch.append(
                (2, (self.index(item_), item_.to_dict())),
            )
            x_position = item_.get_xposition()
            y_position = item_.get_yposition() + 2
            xlabel = item_.get_xlabel()
            ylabel = item_.get_ylabel()
            self._remove_item(item_)
        used = self.get_used_positions()
        settings = self.get_application().get_settings_child("figure")
        for position in [x_position, y_position]:
            direction = misc.DIRECTIONS[position]
            item_label = xlabel if position < 2 else ylabel
            axis_label = getattr(settings, f"get_{direction}_label")()
            if not used[position] and item_label == axis_label:
                set_label = getattr(settings, f"set_{direction}_label")
                set_label(settings.get_string(f"{direction}-label"))

        self._add_history_state()

    @staticmethod
    def _on_item_changed(self, item_, prop) -> None:
        self._current_batch.append((
            0,
            (
                item_.get_uuid(),
                prop,
                copy.deepcopy(self._data_copy[item_.get_uuid()][prop]),
                copy.deepcopy(item_.get_property(prop)),
            ),
        ))

    def _on_figure_settings_change(self, figure_settings, param) -> None:
        if param.name in _FIGURE_SETTINGS_HISTORY_IGNORELIST:
            return
        self._current_batch.append((
            4,
            (
                param.name,
                copy.deepcopy(self._figure_settings_copy[param.name]),
                copy.deepcopy(figure_settings.get_property(param.name)),
            ),
        ))

    def _set_data_copy(self) -> None:
        """Set a deep copy for the data."""
        self._current_batch: list = []
        self._data_copy = copy.deepcopy({
            item_.get_uuid(): item_.to_dict()
            for item_ in self
        })
        self._figure_settings_copy = copy.deepcopy({
            prop.replace("_", "-"):
            self.props.figure_settings.get_property(prop)
            for prop in dir(self.props.figure_settings.props)
        })

    def add_history_state_with_limits(self, old_limits: misc.Limits) -> None:
        """Add a state to the clipboard with old_limits set."""
        self._add_history_state(old_limits)

    def _add_history_state(self, old_limits: misc.Limits = None) -> None:
        """Add a state to the clipboard."""
        if not self._current_batch:
            return
        if self._history_pos != -1:
            self._history_states = self._history_states[:self._history_pos + 1]
        self._history_pos = -1
        self._history_states.append(
            (self._current_batch, self.get_figure_settings().get_limits()),
        )
        if old_limits is not None:
            old_state = self._history_states[-2][1]
            for index in range(8):
                old_state[index] = old_limits[index]
        self.props.can_redo = False
        self.props.can_undo = True
        # Keep history states length limited to 100 spots
        if len(self._history_states) > 101:
            self._history_states = self._history_states[1:]
        self._set_data_copy()
        self.props.unsaved = True

    def _undo(self) -> None:
        """Undo the latest change that was added to the clipboard."""
        if not self.props.can_undo:
            return
        batch = self._history_states[self._history_pos][0]
        self._history_pos -= 1
        for change_type, change in reversed(batch):
            if change_type == 0:
                self[change[0]].set_property(change[1], change[2])
            elif change_type == 1:
                self._remove_item(self.get_for_uuid(change["uuid"]))
            elif change_type == 2:
                self._add_item(
                    item.new_from_dict(copy.deepcopy(change[1])),
                    change[0],
                    True,
                )
            elif change_type == 3:
                self.change_position(change[0], change[1])
            elif change_type == 4:
                self.props.figure_settings.set_property(
                    change[0],
                    change[1],
                )
        self.notify("items_selected")
        self.get_figure_settings().set_limits(
            self._history_states[self._history_pos][1],
        )
        self.props.can_redo = True
        self.props.can_undo = \
            abs(self._history_pos) < len(self._history_states)
        self._set_data_copy()
        self._add_view_history_state()

    def _redo(self) -> None:
        """Redo the latest change that was added to the clipboard."""
        if not self.props.can_redo:
            return
        self._history_pos += 1
        state = self._history_states[self._history_pos]
        for change_type, change in state[0]:
            if change_type == 0:
                self[change[0]].set_property(change[1], change[3])
            elif change_type == 1:
                self._add_item(
                    item.new_from_dict(copy.deepcopy(change)),
                    -1,
                    True,
                )
            elif change_type == 2:
                self._remove_item(self.get_for_uuid(change[1]["uuid"]))
            elif change_type == 3:
                self.change_position(change[1], change[0])
            elif change_type == 4:
                self.props.figure_settings.set_property(
                    change[0],
                    change[2],
                )
        self.notify("items_selected")
        self.get_figure_settings().set_limits(state[1])
        self.props.can_redo = self._history_pos < -1
        self.props.can_undo = True
        self._set_data_copy()
        self._add_view_history_state()

    def _add_view_history_state(self) -> None:
        """Add the view to the view history."""
        limits = self.get_figure_settings().get_limits()
        if all(
            math.isclose(old, new) for old,
            new in zip(self._view_history_states[-1], limits)
        ):
            return
        # If a couple of redo's were performed previously, it deletes the
        # clipboard data that is located after the current clipboard
        # position and disables the redo button
        if self._view_history_pos != -1:
            self._view_history_states = \
                self._view_history_states[:self._view_history_pos + 1]
        self._view_history_pos = -1
        self._view_history_states.append(limits)
        self.props.can_view_back = True
        self.props.can_view_forward = False
        self.props.unsaved = True

    def _view_back(self) -> None:
        """Move the view to the previous value in the view history."""
        if not self.props.can_view_back:
            return
        self._view_history_pos -= 1
        self.get_figure_settings().set_limits(
            self._view_history_states[self._view_history_pos],
        )
        self.props.can_view_forward = True
        self.props.can_view_back = \
            abs(self._view_history_pos) < len(self._view_history_states)

    def _view_forward(self) -> None:
        """Move the view to the next value in the view history."""
        if not self.props.can_view_forward:
            return
        self._view_history_pos += 1
        self.get_figure_settings().set_limits(
            self._view_history_states[self._view_history_pos],
        )
        self.props.can_view_back = True
        self.props.can_view_forward = self._view_history_pos < -1

    @staticmethod
    def _get_min_max_from_array(xydata: list, scale: int) -> (float, float):
        try:
            xydata = xydata[numpy.isfinite(xydata)]
        except TypeError:
            return None
        nonzero_data = numpy.array([value for value in xydata if value != 0])
        min_value = nonzero_data.min() if scale in (1, 4) \
            and len(nonzero_data) > 0 else xydata.min()
        max_value = xydata.max()
        return min_value, max_value

    def _optimize_limits(self) -> None:
        """Optimize the limits of the canvas to the data class."""
        figure_settings = self.get_figure_settings()
        axes = [[
            direction,
            False,
            [],
            [],
            figure_settings.get_property(f"{direction}_scale"),
        ] for direction in ("bottom", "left", "top", "right")]
        equation_items = []
        for item_ in self:
            if not isinstance(item_, (item.DataItem, item.EquationItem)) or (
                not item_.get_selected()
                and figure_settings.get_hide_unselected()
            ):
                continue
            if isinstance(item_, item.EquationItem):
                equation_items.append(item_)
                continue
            for index in \
                    item_.get_xposition() * 2, 1 + item_.get_yposition() * 2:
                axis = axes[index]
                axis[1] = True

                xdata = copy.deepcopy(item_.xdata)
                ydata = copy.deepcopy(item_.ydata)

                min_max = self._get_min_max_from_array(
                    numpy.asarray(ydata if index % 2 else xdata),
                    axis[4],
                )
                if min_max is None:
                    return
                min_value, max_value = min_max
                axis[2].append(min_value)
                axis[3].append(max_value)

        for item_ in equation_items:
            xaxis = axes[item_.get_xposition() * 2]
            yaxis = axes[1 + item_.get_yposition() * 2]
            if xaxis[1]:
                x_limits = [min(xaxis[2]), max(xaxis[3])]
            else:
                direction = xaxis[0]
                x_limits = [
                    figure_settings.get_property(f"min_{direction}"),
                    figure_settings.get_property(f"max_{direction}"),
                ]
            yaxis[1] = True

            ydata = utilities.equation_to_data(item_.equation, x_limits)[1]

            min_max = self._get_min_max_from_array(
                numpy.asarray(ydata),
                yaxis[4],
            )
            if min_max is None:
                return
            min_value, max_value = min_max
            yaxis[2].append(min_value)
            yaxis[3].append(max_value)

        for count, (direction, used, min_all, max_all, scale) in \
                enumerate(axes):
            if not used:
                continue
            min_all = min(min_all)
            max_all = max(max_all)
            if scale != 1:  # For non-logarithmic scales
                span = max_all - min_all
                # 0.05 padding on y-axis, 0.015 padding on x-axis
                padding_factor = 0.05 if count % 2 else 0.015
                if isinstance(item_, item.EquationItem) and not count % 2:
                    padding_factor = 0
                max_all += padding_factor * span

                # For inverse scale, calculate padding using a factor
                min_all = (
                    min_all - padding_factor * span if scale != 4 else min_all
                    * 0.99
                )
            else:  # Use different scaling type for logarithmic scale
                # Use padding factor of 2 for y-axis, 1.025 for x-axis
                padding_factor = 2 if count % 2 else 1.025
                if isinstance(item_, item.EquationItem) and not count % 2:
                    padding_factor = 0
                min_all *= 1 / padding_factor
                max_all *= padding_factor
            figure_settings.set_property(f"min_{direction}", min_all)
            figure_settings.set_property(f"max_{direction}", max_all)
        self._add_view_history_state()

    def get_project_dict(self) -> dict:
        """Convert data to dict."""
        figure_settings = self.get_figure_settings()
        return {
            "version": self.get_version(),
            "data": [item_.to_dict() for item_ in self],
            "figure-settings": {
                key: figure_settings.get_property(key)
                for key in dir(figure_settings.props)
            },
            "history-states": self._history_states,
            "history-position": self._history_pos,
            "view-history-states": self._view_history_states,
            "view-history-position": self._view_history_pos,
        }

    def load_from_project_dict(self, project_dict: dict) -> None:
        """Load data from dict."""
        # Load data
        figure_settings = self.get_figure_settings()
        for key, value in project_dict["figure-settings"].items():
            if figure_settings.get_property(key) != value:
                figure_settings.set_property(key, value)
        self.set_items([item.new_from_dict(d) for d in project_dict["data"]])

        # Set clipboard
        self._set_data_copy()
        self._history_states = project_dict["history-states"]
        self._history_pos = project_dict["history-position"]
        self._view_history_states = project_dict["view-history-states"]
        self._view_history_pos = project_dict["view-history-position"]
        self.unsaved = False

        # Set clipboard/view buttons
        self.props.can_undo = \
            abs(self._history_pos) < len(self._history_states)
        self.props.can_redo = self._history_pos < -1
        self.props.can_view_back = \
            abs(self._view_history_pos) < len(self._view_history_states)
        self.props.can_view_forward = self._view_history_pos < -1

    def _save(self) -> None:
        project.save_project_dict(self.props.file, self.get_project_dict())
        self.set_unsaved(False)

    def _load(self) -> None:
        self.load_from_project_dict(project.read_project_file(self.props.file))
        self.set_unsaved(False)
