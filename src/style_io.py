# SPDX-License-Identifier: GPL-3.0-or-later
import io
import logging
from gettext import gettext as _

from PIL import Image

from gi.repository import GLib, Gdk, GdkPixbuf, Gio

from graphs import file_io, utilities

from matplotlib import RcParams, cbook, rc_context
from matplotlib.figure import Figure
from matplotlib.font_manager import font_scalings, weight_dict
from matplotlib.style.core import STYLE_BLACKLIST

import numpy


STYLE_IGNORELIST = [
    "savefig.dpi", "savefig.facecolor", "savefig.edgecolor", "savefig.format",
    "savefix.bbox", "savefig.pad_inches", "savefig.transparent",
    "savefig.orientation",
]
FONT_SIZE_KEYS = [
    "font.size", "axes.labelsize", "xtick.labelsize", "ytick.labelsize",
    "legend.fontsize", "figure.labelsize", "figure.titlesize",
    "axes.titlesize",
]


def parse(file: Gio.File) -> (RcParams, str):
    """
    Parse a style to RcParams.

    This is an improved version of matplotlibs '_rc_params_in_file()' function.
    It is also modified to work with GFile instead of the python builtin
    functions.
    """
    style = RcParams()
    filename = utilities.get_filename(file)
    try:
        wrapper = file_io.open_wrapped(file, "rt")
        for line_number, line in enumerate(wrapper, 1):
            line = line.strip()
            if line_number == 2:
                name = line[2:]
            line = cbook._strip_comment(line)
            if not line:
                continue
            try:
                key, value = line.split(":", 1)
            except ValueError:
                logging.warning(
                    _("Missing colon in file {}, line {}").format(
                        filename, line_number))
                continue
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]  # strip double quotes
            if key in STYLE_BLACKLIST:
                message = _("Non-style related parameter {} in file {}")
                logging.warning(message.format(key, filename))
            elif key in STYLE_IGNORELIST:
                message = _("Ignoring parameter {} in file {}")
                logging.warning(message.format(key, filename))
            elif key in style:
                message = _("Duplicate key in file {}, on line {}")
                logging.warning(message.format(filename, line_number))
            else:
                if key in FONT_SIZE_KEYS \
                        and not value.replace(".", "", 1).isdigit():
                    try:
                        value = font_scalings[value]
                    except KeyError:
                        continue
                elif key == "font.weight" and not value.isdigit():
                    try:
                        value = weight_dict[value]
                    except KeyError:
                        continue
                try:
                    style[key] = value
                except (KeyError, ValueError):
                    message = _("Bad value in file {} on line {}")
                    logging.exception(
                        message.format(filename, line_number))
    except UnicodeDecodeError:
        logging.exception(_("Could not parse {}").format(filename))
    finally:
        wrapper.close()
    return style, name


WRITE_IGNORELIST = STYLE_IGNORELIST + [
    "lines.dashdot_pattern", "lines.dashed_pattern",
    "lines.dotted_pattern", "lines.dash_capstyle", "lines.dash_joinstyle",
    "lines.solid_capstyle", "lines.solid_joinstyle",
]


def write(file: Gio.File, name: str, style: RcParams):
    with file_io.open_wrapped(file, "wt") as wrapper:
        wrapper.write("# Generated via Graphs\n")
        wrapper.write(f"# {name}\n")
        for key, value in style.items():
            if key not in STYLE_BLACKLIST and key not in WRITE_IGNORELIST:
                value = str(value).replace("#", "")
                if key != "axes.prop_cycle":
                    value = value.replace("[", "").replace("]", "")
                    value = value.replace("'", "").replace("'", "")
                    value = value.replace('"', "").replace('"', "")
                wrapper.write(f"{key}: {value}\n")


_PREVIEW_XDATA = numpy.linspace(0, 10, 30)
_PREVIEW_YDATA1 = numpy.sin(_PREVIEW_XDATA)
_PREVIEW_YDATA2 = numpy.cos(_PREVIEW_XDATA)


def _create_preview(style: RcParams, file_format: str = "svg"):
    buffer = io.BytesIO()
    with rc_context(style):
        # set render size in inch
        figure = Figure(figsize=(5, 3))
        axis = figure.add_subplot()
        axis.spines.bottom.set_visible(True)
        axis.spines.left.set_visible(True)
        if not style["axes.spines.top"]:
            axis.tick_params(which="both", top=False, right=False)
        axis.plot(_PREVIEW_XDATA, _PREVIEW_YDATA1)
        axis.plot(_PREVIEW_XDATA, _PREVIEW_YDATA2)
        axis.set_xlabel(_("X Label"))
        axis.set_xlabel(_("Y Label"))
        figure.savefig(buffer, format=file_format)
    return buffer


def generate_preview(style: RcParams) -> Gdk.Texture:
    return Gdk.Texture.new_from_bytes(
        GLib.Bytes.new(_create_preview(style).getvalue()),
    )


def generate_system_preview(
    light_style: RcParams, dark_style: RcParams,
) -> Gdk.Texture:

    def _style_to_array(style):
        return numpy.array(
            Image.open(_create_preview(style, file_format="png")),
        )

    light_image = _style_to_array(light_style)
    dark_image = _style_to_array(dark_style)
    assert light_image.shape == dark_image.shape

    height, width = light_image.shape[0:2]
    stitched_image = Image.fromarray(numpy.concatenate((
        light_image[:, :width // 2],
        dark_image[:, width // 2:],
    ), axis=1))

    return Gdk.Texture.new_for_pixbuf(GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(stitched_image.tobytes()),
        0,
        True,
        8,
        width,
        height,
        width * 4,
    ))
