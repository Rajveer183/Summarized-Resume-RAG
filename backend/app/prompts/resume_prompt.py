"""
Resume generation prompt — universal template for all 24 categories.

Instructs the LLM to synthesize patterns from multiple retrieved resumes
into one generalized, anonymized resume with fixed section order.
"""

from backend.app.utils.category_titles import get_professional_title

SYSTEM_PROMPT = """You are an expert resume writer creating ONE generalized professional resume per job category.

You receive anonymized excerpts from many resumes in the same category. Your job is to:
1. Identify common skills, tools, responsibilities, projects, education patterns, and certifications.
2. Synthesize a single average professional profile — NOT a summary of one resume.
3. Never copy full sentences verbatim from the context.
4. Never include personal information.

STRICT ANONYMIZATION — ALWAYS USE:
- Do NOT output a person name or contact line at the top — only the === CANDIDATE TITLE === section with the professional title
- Companies: XYZ Company, ABC Company, DEF Company (exactly these three, in order)
- University: XYZ University
- Certifications: XYZ Certification, XYZ Professional Certification, XYZ Domain Certification

NEVER INCLUDE:
- Real names, emails, phones, addresses, LinkedIn, GitHub, portfolio URLs
- Real company or university names
- Any dates (years, months, ranges like 2019-Present)
- Experience duration (no "5 years", "8+ years experience")
- Senior, Junior, Lead, Expert, Fresher, Intern in the job title
- Exact numbers or awards copied from source resumes
- Unique project or company names from sources

JOB TITLE RULE:
Use EXACTLY the professional title provided in the user message (e.g., "Professional Business Development Manager").
Do not modify it.

GENERATION STYLE:
- temperature-equivalent: factual, consistent, professional
- Generalize responsibilities; use category-appropriate language
- Skills must reflect the most common tools/technologies in the context
"""

RESUME_GENERATION_PROMPT = """Generate a complete generalized resume for category: **{category}**

Required job title line (use EXACTLY, do not change):
**{professional_title}**

Reference context from multiple resumes in this category (patterns only — do not copy verbatim):

--- CONTEXT START ---
{context}
--- CONTEXT END ---

Output the resume using EXACTLY these section markers and structure. No extra sections. No markdown headers other than === markers.

=== CANDIDATE TITLE ===
{professional_title}

=== PROFESSIONAL SUMMARY ===
[3-4 sentences. Results-driven professional skilled in category-relevant capabilities. Mention common skills and responsibilities from context. No years, no companies, no personal achievements.]

=== TECHNICAL SKILLS ===
[Exactly 3 skill subcategories appropriate for {category_display}. Format EACH subcategory as:]

Subcategory Name
• skill one
• skill two
• skill three

[Repeat for 3 subcategories. Use the most frequent skills from context. Bullets only under each subcategory.]

=== WORK EXPERIENCE ===
XYZ Company
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]

ABC Company
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]

DEF Company
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]
• [generalized responsibility bullet]

[No dates. No job titles at companies. Only company name then bullets.]

=== PROJECTS ===
[Exactly 2 projects. Format each as:]

Project Title
[2-3 sentence generalized description based on common project patterns in context.]

Technologies/skills used: [comma-separated tools]

[Second project with same format. No personal or company-specific project names.]

=== EDUCATION ===
XYZ University
[One line: common degree field for this category, e.g., "Business Administration or related field" — no dates, no grades, no real university names.]

=== CERTIFICATIONS ===
• XYZ Certification
• XYZ Professional Certification
• XYZ Domain Certification

=== ACHIEVEMENTS ===
• [generalized professional achievement — delivery/quality/collaboration]
• [generalized professional achievement — problem solving/optimization]
• [generalized professional achievement — no copied metrics from context]
• [generalized professional achievement — team/process improvement]

Remember: synthesize from ALL context patterns; one universal template; zero personal data; zero dates.
"""


def build_prompt(category: str, context_chunks: list) -> tuple[str, str]:
    """
    Build the system and user prompts for resume generation.

    Args:
        category: The job category (e.g., "INFORMATION-TECHNOLOGY")
        context_chunks: List of chunk dicts from retriever/reranker

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    category_display = category.replace("-", " ").replace("_", " ").title()
    professional_title = get_professional_title(category)

    section_order = [
        "Summary",
        "Skills",
        "Experience",
        "Projects",
        "Education",
        "Certifications",
        "Achievements",
        "General",
        "Preamble",
    ]

    section_chunks: dict = {}
    for chunk in context_chunks:
        section = chunk["metadata"].get("section_name", "General")
        section_chunks.setdefault(section, []).append(chunk["text"])

    context_parts = []
    for section in section_order:
        if section in section_chunks:
            context_parts.append(f"[{section.upper()}]")
            context_parts.extend(section_chunks[section])
            context_parts.append("")

    for section, texts in section_chunks.items():
        if section not in section_order:
            context_parts.append(f"[{section.upper()}]")
            context_parts.extend(texts)
            context_parts.append("")

    context_str = "\n".join(context_parts)

    user_prompt = RESUME_GENERATION_PROMPT.format(
        category=category,
        category_display=category_display,
        professional_title=professional_title,
        context=context_str,
    )

    return SYSTEM_PROMPT, user_prompt
