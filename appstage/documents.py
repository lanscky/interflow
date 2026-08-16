from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
import hashlib
import json


def certificate_data_hash(affectation, evaluation):
    user = affectation.student.user
    payload = {
        'student': [user.prenom, user.postnom, user.username],
        'company': affectation.offre_stage.company.name,
        'title': affectation.offre_stage.title,
        'start_date': affectation.start_date.isoformat() if affectation.start_date else None,
        'end_date': affectation.end_date.isoformat() if affectation.end_date else None,
        'supervisor_name': affectation.supervisor_name,
        'score': evaluation.score,
        'comments': evaluation.comments,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def build_stage_certificate(affectation, evaluation, reference, verification_url):
    buffer = BytesIO()
    page_size = landscape(A4)
    student_user = affectation.student.user
    student_name = " ".join(filter(None, [
        student_user.prenom,
        student_user.postnom,
        student_user.username,
    ]))
    company_name = affectation.offre_stage.company.name
    safe_student_name = escape(student_name)
    safe_company_name = escape(company_name)
    safe_title = escape(affectation.offre_stage.title)
    safe_comments = escape(evaluation.comments)

    qr_code = qr.QrCodeWidget(verification_url)
    qr_bounds = qr_code.getBounds()
    qr_width = qr_bounds[2] - qr_bounds[0]
    qr_height = qr_bounds[3] - qr_bounds[1]
    qr_size = 25 * mm
    qr_drawing = Drawing(qr_size, qr_size, transform=[
        qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0,
    ])
    qr_drawing.add(qr_code)

    def decorate(canvas, document):
        width, height = page_size
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#044EB8"))
        canvas.setLineWidth(3)
        canvas.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
        canvas.setStrokeColor(colors.HexColor("#1B81CA"))
        canvas.setLineWidth(0.8)
        canvas.rect(16 * mm, 16 * mm, width - 32 * mm, height - 32 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawCentredString(width / 2, 9 * mm, f"Référence de vérification : {reference}")
        canvas.restoreState()

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "CertificateTitle", parent=styles["Title"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=25, leading=30,
        textColor=colors.HexColor("#044EB8"), spaceAfter=5 * mm,
    )
    centered = ParagraphStyle(
        "Centered", parent=styles["BodyText"], alignment=TA_CENTER,
        fontName="Helvetica", fontSize=13, leading=21,
        textColor=colors.HexColor("#1D2633"),
    )
    name_style = ParagraphStyle(
        "StudentName", parent=centered, fontName="Helvetica-Bold",
        fontSize=20, leading=25, textColor=colors.HexColor("#111827"),
    )
    small = ParagraphStyle(
        "SmallCentered", parent=centered, fontSize=10, leading=15,
        textColor=colors.HexColor("#667085"),
    )

    story = [
        Spacer(1, 12 * mm),
        Paragraph("TOTINDA", ParagraphStyle("Brand", parent=title, fontSize=13, leading=16, spaceAfter=4 * mm)),
        Paragraph("ATTESTATION DE FIN DE STAGE", title),
        Paragraph(f"L’entreprise <b>{safe_company_name}</b> atteste que", centered),
        Spacer(1, 4 * mm),
        Paragraph(safe_student_name, name_style),
        Spacer(1, 4 * mm),
        Paragraph(
            f"a effectué avec succès un stage en qualité de <b>{safe_title}</b>, "
            f"du <b>{affectation.start_date.strftime('%d/%m/%Y')}</b> au "
            f"<b>{affectation.end_date.strftime('%d/%m/%Y')}</b>.",
            centered,
        ),
        Spacer(1, 5 * mm),
        Table(
            [["Note finale", f"{evaluation.score} / 10"],
             ["Appréciation", Paragraph(safe_comments, small)]],
            colWidths=[38 * mm, 125 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF4FF")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#044EB8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]),
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            f"Délivrée par {safe_company_name} le {evaluation.created_at.strftime('%d/%m/%Y')}.",
            small,
        ),
        Paragraph(
            f"Superviseur : {affectation.supervisor_name or 'Responsable de stage'}",
            small,
        ),
        Spacer(1, 2 * mm),
        Table(
            [[qr_drawing, Paragraph(
                f"Scannez ce QR code pour vérifier l’authenticité du document.<br/>"
                f"<b>{escape(reference)}</b>", small,
            )]],
            colWidths=[30 * mm, 90 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]),
        ),
    ]

    document = SimpleDocTemplate(
        buffer, pagesize=page_size,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Attestation de stage - {student_name}",
        author=company_name,
    )
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue(), reference
