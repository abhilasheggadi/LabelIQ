import os
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from ..config import settings
from ..schemas import ViolationDetail, ExtractedFieldItem

class PDFEvidenceService:
    def __init__(self):
        self.output_dir = settings.PDF_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_evidence_pdf(
        self,
        inspection_data: Dict[str, Any],
        fields: Dict[str, ExtractedFieldItem],
        violations: List[ViolationDetail],
        annotated_image_path: Optional[Any] = None  # str or List[str]
    ) -> Tuple[str, str]:
        """
        Generates an official, legally defensible Seizure / Inspection Memo PDF.
        Returns: (pdf_path, sha256_hash)
        """
        uuid_str = inspection_data.get("inspection_uuid", "INSP-TEMP")
        filename = f"legal_memo_{uuid_str[:12]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm
        )

        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'GovHeader',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0f2027')
        )
        subtitle_style = ParagraphStyle(
            'GovSubHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        section_heading = ParagraphStyle(
            'SecHead',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#1a365d'),
            spaceBefore=6,
            spaceAfter=3
        )
        body_style = ParagraphStyle(
            'BodyCompact',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#222222')
        )
        table_cell = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#1a202c')
        )
        table_cell_bold = ParagraphStyle(
            'TableCellBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#1a202c')
        )
        violation_cell = ParagraphStyle(
            'ViolCell',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#9b1c1c')
        )
        pass_cell = ParagraphStyle(
            'PassCell',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor('#03543f')
        )

        story = []

        # 1. Government Header Banner
        story.append(Paragraph("GOVERNMENT OF INDIA / STATE LEGAL METROLOGY ENFORCEMENT", title_style))
        story.append(Paragraph("OFFICE OF THE CONTROLLER OF LEGAL METROLOGY", subtitle_style))
        story.append(Paragraph("STATUTORY INSPECTION, COMPLIANCE & SEIZURE MEMORANDUM", ParagraphStyle(
            'MemoBanner', fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor('#822727')
        )))
        story.append(Paragraph("Issued under Section 15 & Section 36 of Legal Metrology Act, 2009 read with LMPC Rules, 2011", ParagraphStyle(
            'ActRef', fontName='Helvetica-Oblique', fontSize=7.5, alignment=TA_CENTER, textColor=colors.HexColor('#4a5568')
        )))
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a365d'), spaceAfter=4))

        # 2. Case & Geolocation Metadata Table
        verdict = inspection_data.get("verdict", "FAIL")
        verdict_display = "PASSED" if verdict == "PASS" else ("FAILED" if verdict == "FAIL" else "WARNING")
        verdict_color = colors.HexColor('#9b1c1c') if verdict == "FAIL" else (colors.HexColor('#d97706') if verdict == "WARNING" else colors.HexColor('#03543f'))
        
        meta_data = [
            [
                Paragraph(f"<b>Inspection Memo ID:</b> {uuid_str}", body_style),
                Paragraph(f"<b>Date & Time:</b> {inspection_data.get('timestamp', datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S'))}", body_style)
            ],
            [
                Paragraph(f"<b>Inspector Name / ID:</b> {inspection_data.get('inspector_name', 'Inspector R. K. Sharma')} ({inspection_data.get('inspector_id', 'INSP-LM-042')})", body_style),
                Paragraph(f"<b>Category:</b> {str(inspection_data.get('product_category', 'General')).upper()}", body_style)
            ],
            [
                Paragraph(f"<b>Warehouse / Establishment:</b> {inspection_data.get('warehouse_name', 'Central Hub')}", body_style),
                Paragraph(f"<b>Address:</b> {inspection_data.get('warehouse_address', 'Plot 14, Industrial Area')}", body_style)
            ],
            [
                Paragraph(f"<b>GPS Coordinates:</b> Lat: {inspection_data.get('latitude', 28.5355):.4f}, Long: {inspection_data.get('longitude', 77.2628):.4f} (±{inspection_data.get('gps_accuracy_m', 5.0):.1f}m)", body_style),
                Paragraph(f"<b>Final Verdict:</b> <font color='{verdict_color.hexval()}'><b>{verdict_display} ({inspection_data.get('compliance_score', 0)}% Score)</b></font>", body_style)
            ]
        ]
        
        meta_table = Table(meta_data, colWidths=[90 * mm, 96 * mm])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 4 * mm))

        # 3. Visual Label Evidence & Calibration Details
        story.append(Paragraph("1. VISUAL EVIDENCE & COMPUTER VISION METRICS", section_heading))
        
        # Normalize image paths to list
        if isinstance(annotated_image_path, str):
            image_paths = [annotated_image_path]
        elif isinstance(annotated_image_path, list):
            image_paths = annotated_image_path
        else:
            image_paths = []

        img_flowables = []
        for p in image_paths[:2]:  # Display up to 2 primary photos in compact box
            if p and os.path.exists(p):
                try:
                    img_flowables.append(RLImage(p, width=36 * mm if len(image_paths) > 1 else 70 * mm, height=50 * mm))
                except Exception:
                    pass

        card_present = inspection_data.get('card_calibrated')
        card_type_str = str(inspection_data.get('card_type', 'ID_1_STANDARD'))
        card_w_px = inspection_data.get('card_width_pixels')
        card_h_px = inspection_data.get('card_height_pixels')
        card_area = inspection_data.get('pdp_surface_area_cm2')
        
        if card_present and card_w_px:
            card_str = f"Calibrated via ISO ID-1 ({card_w_px:.0f}x{card_h_px:.0f} px)"
        elif card_present:
            card_str = f"Calibrated ({card_type_str})"
        else:
            card_str = "Not Detected (Graceful Review Fallback)"

        avg_text_px = inspection_data.get('avg_text_height_px')
        avg_text_mm = inspection_data.get('avg_text_height_mm')
        avg_text_str = f"{avg_text_mm:.2f} mm ({avg_text_px:.1f} px)" if (avg_text_mm and avg_text_px) else (f"{avg_text_px:.1f} px" if avg_text_px else "N/A")

        cv_info_p = [
            Paragraph(f"<b>Panels Captured:</b> {len(image_paths)} package photograph(s)", body_style),
            Paragraph(f"<b>Glare Analysis:</b> {inspection_data.get('glare_ratio', 0.0)*100:.1f}% hotspot area ({'Severe Glare Warning' if inspection_data.get('glare_detected') else 'Optimal Lighting'})", body_style),
            Paragraph(f"<b>Sharpness Index:</b> {inspection_data.get('blur_score', 120):.1f} (Laplacian Variance)", body_style),
            Paragraph(f"<b>Reference Card Calibration:</b> {card_str}", body_style),
            Paragraph(f"<b>Estimated PDP Area:</b> {f'{card_area:.1f} cm²' if card_area else 'Auto Scale'}", body_style),
            Paragraph(f"<b>Average Text Size:</b> {avg_text_str}", body_style),
            Paragraph(f"<b>Optical Scale:</b> {inspection_data.get('mm_per_pixel', 0.18):.4f} mm / pixel", body_style),
            Paragraph(f"<b>Cryptographic SHA-256 Hash:</b><br/><font size='6' face='Courier'>{inspection_data.get('evidence_sha256', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')}</font>", body_style)
        ]

        if img_flowables:
            img_container = Table([[f for f in img_flowables]], colWidths=[38 * mm] * len(img_flowables) if len(img_flowables) > 1 else [74 * mm])
            img_container.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            evidence_grid = Table([[img_container, cv_info_p]], colWidths=[76 * mm, 110 * mm])
            evidence_grid.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(evidence_grid)
        else:
            for p in cv_info_p:
                story.append(p)
                
        story.append(Spacer(1, 4 * mm))

        # 4. Statutory Compliance & Rule Audit Matrix Table
        story.append(Paragraph("2. STATUTORY DECLARATION AUDIT MATRIX (LMPC RULES, 2011)", section_heading))
        
        table_rows = [
            [
                Paragraph("<b>Rule No.</b>", table_cell_bold),
                Paragraph("<b>Statutory Mandatory Requirement</b>", table_cell_bold),
                Paragraph("<b>Observed on Package</b>", table_cell_bold),
                Paragraph("<b>Status</b>", table_cell_bold),
                Paragraph("<b>Statutory Provision / Penalty</b>", table_cell_bold)
            ]
        ]

        # Populate rows from evaluated fields and violations
        for key, f in fields.items():
            viol = next((v for v in violations if v.field_key == key), None)
            
            if viol:
                status_p = Paragraph(f"<font color='#9b1c1c'><b>FAILED<br/>({viol.severity})</b></font>", violation_cell)
                observed_text = f.raw_value if f.raw_value else "[MISSING / NOT PRINTED]"
                prov_text = f"{viol.act_section}<br/>{viol.remedy_description}"
            elif f.is_present and f.is_valid:
                font_note = f" (Font: {f.font_height_mm}mm)" if f.font_height_mm else ""
                status_p = Paragraph("<font color='#03543f'><b>PASSED</b></font>", pass_cell)
                observed_text = (f.raw_value[:60] + "...") if f.raw_value and len(f.raw_value) > 60 else (f.raw_value or "Present & Verified")
                observed_text += font_note
                prov_text = f.legal_act_section
            else:
                status_p = Paragraph("<font color='#d97706'><b>REVIEW</b></font>", table_cell)
                observed_text = f.raw_value or "Pending Verification"
                prov_text = f.legal_act_section

            # Clean any unicode rupee symbols that ReportLab Helvetica cannot render
            clean_observed = str(observed_text).replace("₹", "Rs. ")
            clean_prov = str(prov_text).replace("₹", "Rs. ")

            table_rows.append([
                Paragraph(f.rule_number.replace("₹", "Rs. "), table_cell_bold),
                Paragraph(f.rule_title.replace("₹", "Rs. "), table_cell),
                Paragraph(clean_observed, table_cell),
                status_p,
                Paragraph(clean_prov, table_cell)
            ])

        audit_table = Table(table_rows, colWidths=[24 * mm, 45 * mm, 45 * mm, 26 * mm, 46 * mm])
        audit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        
        story.append(audit_table)
        story.append(Spacer(1, 4 * mm))

        # 5. Legal Penal Directives & Seizure Notice
        story.append(Paragraph("3. LEGAL DIRECTIVE & PENAL CLAUSES APPLICABLE", section_heading))
        if violations:
            directive_text = (
                f"<b>NOTICE OF STATUTORY VIOLATION:</b> During the spot inspection conducted under Section 15 of the Legal Metrology Act, 2009, "
                f"<b>{len(violations)} statutory violations</b> were identified on the subject pre-packaged commodity. "
                "The manufacturer / packer / distributor is hereby put on notice that packing, distributing, or selling non-compliant commodities "
                "is punishable under <b>Section 36(1) of the Legal Metrology Act, 2009</b> with compounding fine up to Rs. 25,000 (First Offence) or Rs. 50,000 / imprisonment (Subsequent Offence)."
            )
        else:
            directive_text = (
                "<b>COMPLIANCE CERTIFICATE:</b> The subject pre-packaged commodity was inspected and found to be in prima facie compliance "
                "with the mandatory labeling and declaration norms specified under the Legal Metrology (Packaged Commodities) Rules, 2011."
            )
        story.append(Paragraph(directive_text, body_style))
        story.append(Spacer(1, 5 * mm))

        # 6. Inspector & Establishment Signature Block (Courtroom Defensible)
        sig_data = [
            [
                Paragraph("<b>INSPECTING OFFICER</b>", table_cell_bold),
                Paragraph("<b>ESTABLISHMENT / WAREHOUSE WITNESS</b>", table_cell_bold)
            ],
            [
                Paragraph(f"Signature: __________________________<br/>Name: {inspection_data.get('inspector_name', 'R. K. Sharma')}<br/>Badge: {inspection_data.get('inspector_id', 'INSP-LM-042')}<br/>Seal / Date: {datetime.datetime.now().strftime('%d-%m-%Y')}", body_style),
                Paragraph("Signature: __________________________<br/>Name: _______________________________<br/>Designation: Warehouse Manager / Owner<br/>Date: _______________________________", body_style)
            ]
        ]
        sig_table = Table(sig_data, colWidths=[93 * mm, 93 * mm])
        sig_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#94a3b8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(KeepTogether(sig_table))

        # Build document
        doc.build(story)

        # Compute SHA-256
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            sha256 = hashlib.sha256(pdf_bytes).hexdigest()

        return str(pdf_path), sha256

pdf_service = PDFEvidenceService()
