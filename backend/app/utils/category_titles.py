"""
Maps dataset category folder names to standardized professional job titles.
Format: Professional <Job Title> (no Senior/Junior/Lead/Expert/Fresher/Intern).
"""
from typing import Dict

CATEGORY_JOB_TITLES: Dict[str, str] = {
    "ACCOUNTANT": "Professional Accountant",
    "ADVOCATE": "Professional Legal Advocate",
    "AGRICULTURE": "Professional Agriculture Specialist",
    "APPAREL": "Professional Apparel Industry Specialist",
    "ARTS": "Professional Arts Professional",
    "AUTOMOBILE": "Professional Automobile Industry Specialist",
    "AVIATION": "Professional Aviation Specialist",
    "BANKING": "Professional Banking Professional",
    "BPO": "Professional BPO Operations Specialist",
    "BUSINESS-DEVELOPMENT": "Professional Business Development Manager",
    "CHEF": "Professional Chef",
    "CONSTRUCTION": "Professional Construction Specialist",
    "CONSULTANT": "Professional Consultant",
    "DESIGNER": "Professional Designer",
    "DIGITAL-MEDIA": "Professional Digital Media Specialist",
    "ENGINEERING": "Professional Engineer",
    "FINANCE": "Professional Finance Specialist",
    "FITNESS": "Professional Fitness Specialist",
    "HEALTHCARE": "Professional Healthcare Specialist",
    "HR": "Professional Human Resource Specialist",
    "INFORMATION-TECHNOLOGY": "Professional Information Technology Specialist",
    "PUBLIC-RELATIONS": "Professional Public Relations Specialist",
    "SALES": "Professional Sales Executive",
    "TEACHER": "Professional Teacher",
}


def get_professional_title(category: str) -> str:
    """Return the universal job title line for a category."""
    key = category.strip().upper().replace(" ", "-")
    if key in CATEGORY_JOB_TITLES:
        return CATEGORY_JOB_TITLES[key]
    display = key.replace("-", " ").title()
    return f"Professional {display} Specialist"
