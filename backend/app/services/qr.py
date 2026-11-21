"""The QR code of a permit (PRD Section 8).

The QR holds plain text that any scanner shows without a network, and a short
verification link. The text is kept short so that the printed code has large
squares and scans reliably through a windscreen.
"""

import base64

import segno

from app.core.config import get_settings
from app.models import Application

# The picnic spot is cut to this length in the QR text. The permit prints it in full.
DESTINATION_MAX = 40
# Error correction "M": a good balance between square size and tolerance of dirt or glare.
ERROR_LEVEL = "m"
# The white margin a scanner needs around the code, in squares.
QUIET_ZONE = 4


def verify_url(application: Application) -> str:
    """The short public link that shows the live status of the permit."""
    return f"{get_settings().public_base_url}/v/{application.verify_code}"


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def text(application: Application) -> str:
    """The plain text of the QR code, one fact per line."""
    a = application
    return "\n".join(
        [
            f"PICNIC PERMIT {a.application_number}",
            f"{a.travel_date:%d-%m-%Y} {a.departure_time:%H:%M}-{a.return_time:%H:%M}",
            f"Veh {a.vehicle_reg_number}",
            f"Drv {_short(a.driver_name, 40)}, DL {a.licence_number}",
            f"People {a.total_people}",
            f"From {a.origin_police_station.name}, {a.origin_district.name}",
            f"To {_short(a.destination_address, DESTINATION_MAX)}, {a.destination_district.name}",
            f"Ldr {a.leader_mobile}",
            verify_url(a),
        ]
    )


def make(application: Application) -> segno.QRCode:
    return segno.make(text(application), error=ERROR_LEVEL, micro=False)


def printed_size_cm(code: segno.QRCode, *, squares_cm: float) -> float:
    """The side of the printed image, margin included, when the code itself is `squares_cm` wide.

    The SOP asks for a code of at least 10 cm. The margin is added outside it.
    """
    squares = code.symbol_size(scale=1, border=0)[0]
    return squares_cm * (squares + 2 * QUIET_ZONE) / squares


def svg_data_uri(code: segno.QRCode) -> str:
    """The code as an image address that a page or a PDF can show at any size."""
    svg = code.svg_inline(scale=1, border=QUIET_ZONE, omitsize=True)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
