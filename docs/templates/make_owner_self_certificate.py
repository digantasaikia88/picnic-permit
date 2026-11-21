"""Builds the blank Owner's Self-Certificate form offered for download in Step 3.

The wording follows Section 3.2 (Vehicle Owner) of the SOP "Picnic Journeys by
Road: Picnic Season". Edit the text below and run the command again to change
the form. The result is a static file served by the frontend:

    frontend/public/owner-self-certificate.pdf

Run from the project folder (nothing is installed on the computer):

    docker run --rm -v "${PWD}:/work" -w /work python:3.14.10-slim-trixie sh -c "pip install -q reportlab==5.1.0 && python docs/templates/make_owner_self_certificate.py"
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "owner-self-certificate.pdf"

DETAILS = [
    "Name of the registered owner",
    "Address of the owner",
    "Mobile number of the owner",
    "Vehicle registration number",
    "Type of vehicle",
    "Registered seating capacity",
    "Date of the picnic journey",
    "Name of the group leader",
    "Mobile number of the group leader",
]

DECLARATIONS = [
    "The vehicle is not a goods vehicle, truck, tractor or trailer, and is legally eligible "
    "to carry passengers.",
    "The Registration Certificate, motor vehicle insurance, Pollution Under Control "
    "certificate, road tax payment, fitness certificate (where required), vehicle permit "
    "(where required) and Speed Limiting Device certificate (where legally required) are "
    "valid, and will remain valid on the date of the journey.",
    "All unpaid traffic challans relating to the vehicle have been cleared.",
    "The vehicle is mechanically safe and roadworthy, and all required safety devices are "
    "installed and functional.",
    "The vehicle is given to the group leader named above for this journey with my knowledge "
    "and consent.",
    "The vehicle will be used only for the approved journey, and I agree to comply with every "
    "applicable condition of the Standard Operating Procedure "
    "&ldquo;Picnic Journeys by Road: Picnic Season&rdquo;.",
    "I understand that any violation may lead to suspension or cancellation of the vehicle "
    "permit, where applicable and in accordance with law.",
]

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=10.5, leading=14.5)
CENTRE = ParagraphStyle("centre", parent=BASE, alignment=TA_CENTER)
TITLE = ParagraphStyle(
    "title", parent=CENTRE, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceBefore=6
)
SMALL = ParagraphStyle("small", parent=CENTRE, fontSize=9, leading=12, textColor=colors.grey)
BODY = ParagraphStyle("body", parent=BASE, alignment=TA_JUSTIFY)
ITEM = ParagraphStyle("item", parent=BASE, leftIndent=8 * mm, firstLineIndent=-8 * mm, spaceAfter=3)


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(
        A4[0] / 2,
        12 * mm,
        "Picnic Portal · Picnic/Recreational Journey Permit · Transport Department, "
        "Government of Assam",
    )
    canvas.restoreState()


def build() -> None:
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title="Owner's Self-Certificate: Picnic/Recreational Journey Permit",
        author="Transport Department, Government of Assam",
    )

    details = Table(
        [
            [Paragraph(f"{number}. {label}", BASE), ""]
            for number, label in enumerate(DETAILS, start=1)
        ],
        colWidths=[70 * mm, 100 * mm],
        rowHeights=8 * mm,
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEBELOW", (1, 0), (1, -1), 0.6, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    signature = Table(
        [
            [Paragraph("Place:", BASE), "", "", ""],
            [Paragraph("Date:", BASE), "", "", Paragraph("Signature of the registered owner", CENTRE)],
        ],
        colWidths=[16 * mm, 50 * mm, 24 * mm, 80 * mm],
        rowHeights=[9 * mm, 12 * mm],
    )
    signature.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEBELOW", (1, 0), (1, 1), 0.6, colors.black),
                ("LINEABOVE", (3, 1), (3, 1), 0.6, colors.black),
                ("VALIGN", (3, 1), (3, 1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    story = [
        Paragraph("GOVERNMENT OF ASSAM", CENTRE),
        Paragraph("TRANSPORT DEPARTMENT", CENTRE),
        Paragraph("Picnic/Recreational Journey Permit", CENTRE),
        Paragraph("OWNER&rsquo;S SELF-CERTIFICATE", TITLE),
        Paragraph(
            "To be filled and signed by the registered owner of the vehicle, "
            "and uploaded with the application on the Picnic Portal.",
            SMALL,
        ),
        Spacer(1, 5 * mm),
        details,
        Spacer(1, 4 * mm),
        Paragraph("I, the registered owner of the vehicle named above, certify that:", BODY),
        Spacer(1, 2 * mm),
        *[
            Paragraph(f"({letter})&nbsp;&nbsp;{text}", ITEM)
            for letter, text in zip("abcdefgh", DECLARATIONS, strict=False)
        ],
        Spacer(1, 2 * mm),
        Paragraph("The above is true to the best of my knowledge and belief.", BODY),
        Spacer(1, 4 * mm),
        signature,
    ]
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Written {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
