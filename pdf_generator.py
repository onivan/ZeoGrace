from reportlab.lib.pagesizes import A4, A5
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from config import PDF_STYLES
from utils import get_proportional_image
from pdf_components import NumberedCanvas


def build_pdf_document(output_dest, layout_key, style_key, records, filter_text="", font_name="Helvetica", phone_card_height=150):
    style_cfg = PDF_STYLES.get(style_key, PDF_STYLES["slate"])
    styles = getSampleStyleSheet()

    if layout_key == "phone":
        page_size = A5
        left_margin = right_margin = 16
        top_margin = 16
        bottomMargin = 18
        doc_width = page_size[0] - (left_margin + right_margin)
    else:
        page_size = A4
        left_margin = right_margin = 25
        top_margin = 25
        bottomMargin = 25
        doc_width = 545

    doc = SimpleDocTemplate(
        output_dest,
        pagesize=page_size,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottomMargin
    )

    elements = []

    title_font_size = 14 if layout_key == "phone" else 15
    title_style = ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=title_font_size,
        leading=title_font_size + 3,
        spaceAfter=5,
        alignment=1,
        textColor=style_cfg["title_color"]
    )

    filter_style = ParagraphStyle(
        name="ReportFilter",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=6.8 if layout_key == "phone" else 7.5,
        leading=9.5,
        textColor=style_cfg["filter_text_color"]
    )

    elements.append(Paragraph("Звіт списку громади", title_style))
    filter_table = Table([[Paragraph(filter_text, filter_style)]], colWidths=[doc_width])
    filter_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), style_cfg["filter_box_bg"]),
        ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["filter_box_border"]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(filter_table)
    elements.append(Spacer(1, 5))

    # --- 1. А4 Картки ---
    if layout_key == "a4_cards":
        card_w = (doc_width - 8) / 2
        card_photo_max_w = card_w * 0.38
        card_photo_max_h = 165
        info_w = card_w - card_photo_max_w - 8

        text_style = ParagraphStyle(
            name="CardTextA4",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=7.2,
            leading=9.2
        )
        title_card_style = ParagraphStyle(
            name="CardTitleA4",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=8.5,
            leading=10.5,
            textColor=style_cfg["title_color"]
        )

        cards = []
        for idx, rec in enumerate(records, start=1):
            img_widget = get_proportional_image(rec["photo_bytes"], card_photo_max_w, card_photo_max_h)

            info_lines = [
                Paragraph(f"<b>#{idx}. {rec['name']}</b>", title_card_style),
                Paragraph(f"<b>Тел:</b> {rec['phones']}", text_style),
                Paragraph(f"<b>Адреса:</b> {rec['address']}", text_style),
                Paragraph(f"<b>ДН:</b> {rec['dob']} | <b>Хрещ:</b> {rec['bapt']}", text_style),
                Paragraph(f"<b>Статус:</b> {rec['church_status']}", text_style),
                Paragraph(f"<b>Сім'я:</b> {rec['fam_status']} (дітей: {rec['children']})", text_style),
            ]
            if rec["email"]:
                info_lines.append(Paragraph(f"<b>Email:</b> {rec['email']}", text_style))

            card_table = Table([[img_widget, info_lines]], colWidths=[card_photo_max_w, info_w])
            card_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), style_cfg["card_bg"]),
                ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["card_border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            cards.append(card_table)

        grid_data = []
        for i in range(0, len(cards), 2):
            row_cells = [cards[i]]
            if i + 1 < len(cards):
                row_cells.append(cards[i + 1])
            else:
                row_cells.append("")
            grid_data.append(row_cells)

        if grid_data:
            cards_grid = Table(grid_data, colWidths=[card_w, card_w])
            cards_grid.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(cards_grid)

    # --- 2. Для телефону (A5) ---
    elif layout_key == "phone":
        card_w = doc_width
        card_photo_max_h = max(60, phone_card_height - 14)
        card_photo_max_w = min(card_w * 0.48, card_photo_max_h * 0.78)
        info_w = card_w - card_photo_max_w - 8

        font_scale = max(0.85, min(1.30, phone_card_height / 150.0))
        base_font_sz = 7.0 * font_scale
        title_font_sz = 8.6 * font_scale

        phone_text_style = ParagraphStyle(
            name="CardPhoneText",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=base_font_sz,
            leading=base_font_sz * 1.25
        )
        phone_title_style = ParagraphStyle(
            name="CardPhoneTitle",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=title_font_sz,
            leading=title_font_sz * 1.22,
            textColor=style_cfg["title_color"]
        )

        for idx, rec in enumerate(records, start=1):
            img_widget = get_proportional_image(rec["photo_bytes"], card_photo_max_w, card_photo_max_h)

            info_lines = [
                Paragraph(f"<b>#{idx}. {rec['name']}</b>", phone_title_style),
                Paragraph(f"<b>Тел:</b> {rec['phones']}", phone_text_style),
                Paragraph(f"<b>Адреса:</b> {rec['address']}", phone_text_style),
                Paragraph(f"<b>ДН:</b> {rec['dob']} | <b>Хрещ:</b> {rec['bapt']}", phone_text_style),
                Paragraph(f"<b>Статус:</b> {rec['church_status']} | <b>Сім:</b> {rec['fam_status']}", phone_text_style),
                Paragraph(f"<b>Дітей:</b> {rec['children']}", phone_text_style),
            ]
            if rec["email"]:
                info_lines.append(Paragraph(f"<b>Email:</b> {rec['email']}", phone_text_style))

            card_table = Table([[img_widget, info_lines]], colWidths=[card_photo_max_w, info_w])
            card_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), style_cfg["card_bg"]),
                ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["card_border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))

            elements.append(card_table)
            elements.append(Spacer(1, 4))

            if idx % 3 == 0 and idx < len(records):
                elements.append(PageBreak())

    # --- 3. Компактна таблиця ---
    else:
        compact_header_style = ParagraphStyle(
            name="CompactHeader",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=7.5,
            leading=9.5,
            textColor=style_cfg["header_text"]
        )
        compact_cell_style = ParagraphStyle(
            name="CompactCell",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=7.0,
            leading=8.8
        )

        col_widths = [18, 125, 110, 105, 62, 125]
        headers = [
            Paragraph("<b>№</b>", compact_header_style),
            Paragraph("<b>П.І.Б.</b>", compact_header_style),
            Paragraph("<b>Адреса</b>", compact_header_style),
            Paragraph("<b>Номери телефонів</b>", compact_header_style),
            Paragraph("<b>ДН / Хрещення</b>", compact_header_style),
            Paragraph("<b>Додаткові дані (статуси, діти)</b>", compact_header_style)
        ]
        table_data = [headers]

        for idx, rec in enumerate(records, start=1):
            dob_bapt_text = f"{rec['dob']}<br/>{rec['bapt']}" if rec['bapt'] != "—" else rec['dob']

            extras = []
            if rec['church_status'] != "—":
                extras.append(f"Церк: {rec['church_status']}")
            if rec['fam_status'] != "—":
                extras.append(f"Сім'я: {rec['fam_status']}")
            if rec['children']:
                extras.append(f"Дітей: {rec['children']}")
            if rec['email']:
                extras.append(f"{rec['email']}")
            extras_text = " | ".join(extras) if extras else "—"

            table_data.append([
                Paragraph(str(idx), compact_cell_style),
                Paragraph(f"<b>{rec['name']}</b>", compact_cell_style),
                Paragraph(rec['address'], compact_cell_style),
                Paragraph(rec['compact_phones'], compact_cell_style),
                Paragraph(dob_bapt_text, compact_cell_style),
                Paragraph(extras_text, compact_cell_style),
            ])

        compact_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        compact_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), style_cfg["header_bg"]),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, style_cfg["grid_color"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [style_cfg["row_bg1"], style_cfg["row_bg2"]]),
        ]))
        elements.append(compact_table)

    def canvas_factory(*args, **kwargs):
        return NumberedCanvas(*args, font_name=font_name, **kwargs)

    doc.build(elements, canvasmaker=canvas_factory)


def build_families_pdf_document(output_dest, families_data, filter_text="", font_name="Helvetica", style_key="slate"):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from config import PDF_STYLES
    from pdf_components import NumberedCanvas

    style_cfg = PDF_STYLES.get(style_key, PDF_STYLES["slate"])
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        output_dest,
        pagesize=A4,
        leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25
    )

    elements = []

    title_style = ParagraphStyle(
        name="FamReportTitle", parent=styles["Heading1"],
        fontName=font_name, fontSize=15, leading=18, spaceAfter=6,
        alignment=1, textColor=style_cfg["title_color"]
    )
    filter_style = ParagraphStyle(
        name="FamReportFilter", parent=styles["Normal"],
        fontName=font_name, fontSize=7.5, leading=9.5,
        textColor=style_cfg["filter_text_color"]
    )
    fam_header_style = ParagraphStyle(
        name="FamHeaderStyle", parent=styles["Normal"],
        fontName=font_name, fontSize=9, leading=11,
        textColor=style_cfg["header_text"]
    )
    cell_style = ParagraphStyle(
        name="FamCell", parent=styles["Normal"],
        fontName=font_name, fontSize=7.5, leading=9.5
    )

    elements.append(Paragraph("Звіт родин та сімей громади", title_style))

    if filter_text:
        filter_table = Table([[Paragraph(filter_text, filter_style)]], colWidths=[545])
        filter_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), style_cfg["filter_box_bg"]),
            ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["filter_box_border"]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(filter_table)
        elements.append(Spacer(1, 8))

    col_widths = [140, 100, 95, 210]

    for fam_title, members in families_data:
        fam_header = [Paragraph(f"<b>{fam_title}</b>", fam_header_style), "", "", ""]
        table_data = [fam_header]

        for name, role, phone, address in members:
            table_data.append([
                Paragraph(f"<b>{name}</b>", cell_style),
                Paragraph(role, cell_style),
                Paragraph(phone, cell_style),
                Paragraph(address, cell_style),
            ])

        fam_table = Table(table_data, colWidths=col_widths)
        fam_table.setStyle(TableStyle([
            ("SPAN", (0, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (3, 0), style_cfg["header_bg"]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, style_cfg["grid_color"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [style_cfg["row_bg1"], style_cfg["row_bg2"]]),
        ]))

        elements.append(fam_table)
        elements.append(Spacer(1, 8))

    def canvas_factory(*args, **kwargs):
        return NumberedCanvas(*args, font_name=font_name, **kwargs)

    doc.build(elements, canvasmaker=canvas_factory)
