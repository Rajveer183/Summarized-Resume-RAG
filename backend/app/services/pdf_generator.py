"""
PDF Generator Service — converts generated resume text into a PDF file.

Uses one universal template for all categories:
  fixed header, section order, styling, and placeholders.
"""
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from backend.app.config import config
from backend.app.services.resume_sanitizer import (
    enforce_resume_structure,
    sanitize_resume_text,
)
from backend.app.utils.category_titles import get_professional_title
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))


def _extract_section(text: str, section_marker: str) -> str:
    """Extract content between === SECTION === markers."""
    pattern = rf"===\s*{re.escape(section_marker)}\s*===\s*\n(.*?)(?=\n===\s*\w|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _parse_skills(skills_raw: str) -> List[Dict[str, Any]]:
    """Parse skill subcategories with bullet items."""
    groups: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line in skills_raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(("•", "-", "*", "–")):
            item = line.lstrip("•-*– ").strip()
            if current is not None and item:
                current["items"].append(item)
            continue
        if ":" in line and not line.startswith("•"):
            parts = line.split(":", 1)
            groups.append({"category": parts[0].strip(), "items": [parts[1].strip()]})
            current = groups[-1]
            continue
        current = {"category": line.rstrip(":"), "items": []}
        groups.append(current)

    return [g for g in groups if g.get("category") or g.get("items")][:3]


def _parse_experience(experience_raw: str) -> List[Dict[str, Any]]:
    """Parse company blocks (XYZ / ABC / DEF) with bullets only."""
    companies = ("XYZ Company", "ABC Company", "DEF Company")
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line in experience_raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        matched_company = next((c for c in companies if c.upper() in upper or upper == c.upper()), None)
        if matched_company or (
            line.endswith("Company") and not line.startswith(("•", "-"))
        ):
            if current and (current.get("bullets") or current.get("company")):
                entries.append(current)
            current = {
                "company": matched_company or line,
                "title": "",
                "duration": "",
                "bullets": [],
            }
            continue
        if line.startswith(("•", "-", "*", "–")):
            bullet = line.lstrip("•-*– ").strip()
            if current is not None and bullet:
                current["bullets"].append(bullet)
    if current:
        entries.append(current)

    return entries[:3]


def _parse_projects(projects_raw: str) -> List[Dict[str, Any]]:
    """Parse project blocks: title, description, technologies line."""
    blocks = re.split(r"\n\s*\n", projects_raw.strip())
    projects: List[Dict[str, Any]] = []

    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        proj = {"name": "", "description": "", "tech": ""}
        desc_lines: List[str] = []
        for i, line in enumerate(lines):
            lower = line.lower()
            if lower.startswith("technologies/skills used:"):
                proj["tech"] = line.split(":", 1)[-1].strip()
            elif i == 0 and not line.startswith(("•", "-")):
                proj["name"] = line.lstrip("•-* ").strip()
            elif not lower.startswith("technologies"):
                desc_lines.append(line.lstrip("•-* ").strip())
        proj["description"] = " ".join(desc_lines)
        if proj["name"] or proj["description"]:
            projects.append(proj)

    return projects[:2]


def _parse_resume_text(resume_text: str, category: str) -> Dict[str, Any]:
    """Parse structured LLM output into universal template data."""
    title_raw = _extract_section(resume_text, "CANDIDATE TITLE")
    summary_raw = _extract_section(resume_text, "PROFESSIONAL SUMMARY")
    skills_raw = _extract_section(resume_text, "TECHNICAL SKILLS")
    experience_raw = _extract_section(resume_text, "WORK EXPERIENCE")
    projects_raw = _extract_section(resume_text, "PROJECTS")
    education_raw = _extract_section(resume_text, "EDUCATION")
    certifications_raw = _extract_section(resume_text, "CERTIFICATIONS")
    achievements_raw = _extract_section(resume_text, "ACHIEVEMENTS")

    education_field = ""
    for line in education_raw.split("\n"):
        line = line.strip()
        if line and "XYZ University" not in line:
            education_field = line.lstrip("•-* ").strip()
            break

    certifications = [
        line.lstrip("•-*0123456789. ").strip()
        for line in certifications_raw.split("\n")
        if line.strip()
    ]

    achievements = [
        line.lstrip("•-*0123456789. ").strip()
        for line in achievements_raw.split("\n")
        if line.strip()
    ]

    resume_data = {
        "category": category,
        "title": title_raw or get_professional_title(category),
        "summary": summary_raw,
        "skills": _parse_skills(skills_raw),
        "experience": _parse_experience(experience_raw),
        "projects": _parse_projects(projects_raw),
        "education": [
            {
                "degree": education_field or "Relevant academic field or related discipline",
                "institution": "XYZ University",
                "year": "",
            }
        ],
        "certifications": certifications,
        "achievements": achievements,
    }

    return enforce_resume_structure(resume_data, category)


def _generate_with_weasyprint(html_content: str, output_path: Path) -> bool:
    try:
        from weasyprint import HTML

        HTML(string=html_content).write_pdf(str(output_path))
        logger.info(f"PDF generated with WeasyPrint: {output_path.name}")
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"WeasyPrint failed: {e}")
        return False


def _generate_with_reportlab(resume_data: Dict, output_path: Path) -> bool:
    """Generate PDF using ReportLab — universal template layout."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_JUSTIFY
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        primary = colors.HexColor("#0d3b66")
        accent = colors.HexColor("#2c6fad")
        text_body = colors.HexColor("#333333")
        text_light = colors.HexColor("#666666")

        name_style = ParagraphStyle(
            "DesignationTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=primary,
            leading=28,
            spaceAfter=0,
        )
        section_header_style = ParagraphStyle(
            "SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=primary,
            leading=14,
            spaceBefore=14,
            spaceAfter=0,
        )
        body_style = ParagraphStyle(
            "Body",
            fontName="Times-Roman",
            fontSize=10,
            textColor=text_body,
            alignment=TA_JUSTIFY,
            leading=14,
        )
        company_style = ParagraphStyle(
            "Company",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=primary,
            spaceBefore=6,
            spaceAfter=2,
        )
        skill_cat_style = ParagraphStyle(
            "SkillCat",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=primary,
            spaceBefore=4,
        )
        bullet_style = ParagraphStyle(
            "Bullet",
            fontName="Times-Roman",
            fontSize=9.5,
            textColor=text_body,
            leftIndent=14,
            leading=13,
        )
        project_title_style = ParagraphStyle(
            "ProjectTitle",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=primary,
            spaceBefore=6,
        )

        content_width = doc.width

        def add_underline(thickness: float, line_color, top_pad: float, bottom_pad: float):
            """Draw a horizontal rule below preceding text without overlapping it."""
            rule = Table([[""]], colWidths=[content_width], rowHeights=[thickness + top_pad + bottom_pad])
            rule.setStyle(
                TableStyle(
                    [
                        ("LINEBELOW", (0, 0), (-1, -1), thickness, line_color),
                        ("TOPPADDING", (0, 0), (-1, -1), top_pad),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_pad),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(rule)

        story = []

        if resume_data.get("title"):
            story.append(Paragraph(resume_data["title"], name_style))
            add_underline(thickness=2.5, line_color=primary, top_pad=10, bottom_pad=16)

        def add_section_header(title: str):
            story.append(Paragraph(title.upper(), section_header_style))
            add_underline(thickness=0.8, line_color=accent, top_pad=4, bottom_pad=10)

        if resume_data.get("summary"):
            add_section_header("Professional Summary")
            story.append(Paragraph(resume_data["summary"], body_style))
            story.append(Spacer(1, 4))

        if resume_data.get("skills"):
            add_section_header("Technical Skills")
            for skill_group in resume_data["skills"]:
                if skill_group.get("category"):
                    story.append(Paragraph(skill_group["category"], skill_cat_style))
                items = skill_group.get("items", [])
                if isinstance(items, str):
                    items = [i.strip() for i in items.split(",") if i.strip()]
                for item in items:
                    story.append(Paragraph(f"• {item}", bullet_style))
            story.append(Spacer(1, 4))

        if resume_data.get("experience"):
            add_section_header("Work Experience")
            for exp in resume_data["experience"]:
                story.append(Paragraph(exp["company"], company_style))
                for bullet in exp.get("bullets", []):
                    story.append(Paragraph(f"• {bullet}", bullet_style))
            story.append(Spacer(1, 4))

        if resume_data.get("projects"):
            add_section_header("Projects")
            for proj in resume_data["projects"]:
                story.append(Paragraph(proj.get("name", "Project"), project_title_style))
                if proj.get("description"):
                    story.append(Paragraph(proj["description"], body_style))
                if proj.get("tech"):
                    story.append(
                        Paragraph(
                            f"<i>Technologies/skills used: {proj['tech']}</i>",
                            bullet_style,
                        )
                    )
                story.append(Spacer(1, 4))

        if resume_data.get("education"):
            add_section_header("Education")
            for edu in resume_data["education"]:
                story.append(Paragraph(edu["institution"], company_style))
                story.append(Paragraph(edu.get("degree", ""), body_style))
            story.append(Spacer(1, 4))

        if resume_data.get("certifications"):
            add_section_header("Certifications")
            for cert in resume_data["certifications"]:
                story.append(Paragraph(cert, bullet_style))
            story.append(Spacer(1, 4))

        if resume_data.get("achievements"):
            add_section_header("Achievements")
            for ach in resume_data["achievements"]:
                story.append(Paragraph(f"• {ach}", bullet_style))

        doc.build(story)
        logger.info(f"PDF generated with ReportLab: {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"ReportLab PDF generation failed: {e}")
        return False


def generate_pdf(resume_text: str, category: str) -> Optional[Path]:
    """
    Generate a PDF from the LLM resume text output.

    Args:
        resume_text: Structured resume text from LLM (with === SECTION === markers)
        category: Job category name

    Returns:
        Path to the generated PDF file, or None if generation failed
    """
    resume_text = sanitize_resume_text(resume_text, category)
    resume_data = _parse_resume_text(resume_text, category)

    safe_category = category.replace(" ", "_").replace("/", "-")
    filename = f"resume_{safe_category}_{uuid.uuid4().hex[:8]}.pdf"
    output_path = config.GENERATED_RESUMES_PATH / filename

    logger.info(f"Generating PDF: {filename}")

    try:
        template = _jinja_env.get_template("resume_template.html")
        html_content = template.render(**resume_data)
        if _generate_with_weasyprint(html_content, output_path):
            _save_resume_text_sidecar(resume_text, output_path)
            return output_path
    except Exception as e:
        logger.warning(f"HTML template rendering issue: {e}")

    if _generate_with_reportlab(resume_data, output_path):
        _save_resume_text_sidecar(resume_text, output_path)
        return output_path

    logger.error("All PDF generation methods failed")
    return None


def _save_resume_text_sidecar(resume_text: str, pdf_path: Path) -> None:
    """Persist structured resume text alongside PDF for evaluation."""
    try:
        txt_path = pdf_path.with_suffix(".txt")
        txt_path.write_text(resume_text, encoding="utf-8")
    except Exception as e:
        logger.debug(f"Could not save resume text sidecar: {e}")
