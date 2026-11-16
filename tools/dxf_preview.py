"""Draw a DXF as an SVG with ezdxf's own renderer, to look at what a DXF reader sees.

    uv run --isolated --no-project --with ezdxf --with pillow python tools/dxf_preview.py \\
        plan.dxf plan-preview.svg

Then turn the SVG into a PNG with tools/render_svg.py. ezdxf's drawing add-on needs
Pillow, which is not a project dependency, hence the throwaway environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg
from ezdxf.filemanagement import readfile


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    doc = readfile(sys.argv[1])
    backend = svg.SVGBackend()
    settings = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.BLACK,
        lineweight_scaling=2.0,
    )
    Frontend(RenderContext(doc), backend, config=settings).draw_layout(doc.modelspace())
    page = layout.Page(297, 210, layout.Units.mm, margins=layout.Margins.all(10))
    Path(sys.argv[2]).write_text(backend.get_string(page), encoding="utf-8")
    print(f"wrote {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
