/**
 * ResumePreview.jsx — Displays the generated resume with PDF download.
 */
import { Download, FileText } from "lucide-react";
import { getDownloadUrl } from "../api/resumeApi";

const CONTACT_LINE_RE =
  /^\[EMAIL\].*\[PHONE\].*\[URL\]|available for opportunities/i;

function shouldSkipPreviewLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^candidate$/i.test(trimmed)) return true;
  if (CONTACT_LINE_RE.test(trimmed)) return true;
  return false;
}

function renderBodyLines(lines, keyPrefix) {
  return lines.map((line, lineIdx) => {
    const trimmed = line.trim();
    if (!trimmed) return <br key={`${keyPrefix}-${lineIdx}`} />;
    if (trimmed.startsWith("•") || trimmed.startsWith("-") || trimmed.startsWith("*")) {
      return (
        <div key={`${keyPrefix}-${lineIdx}`} className="resume-bullet">
          <span className="bullet-dot">▸</span>
          <span>{trimmed.replace(/^[•\-*]\s*/, "")}</span>
        </div>
      );
    }
    const boldMatch = trimmed.match(/^([A-Za-z ]+:)\s*(.*)/);
    if (boldMatch) {
      return (
        <div key={`${keyPrefix}-${lineIdx}`} className="resume-label-line">
          <strong>{boldMatch[1]}</strong> {boldMatch[2]}
        </div>
      );
    }
    return (
      <p key={`${keyPrefix}-${lineIdx}`} className="resume-text-line">
        {trimmed}
      </p>
    );
  });
}

function formatResumeText(text) {
  const parts = text.split(/(===\s*.+?\s*===)/g);
  const nodes = [];
  let skipNextBody = false;

  for (let idx = 0; idx < parts.length; idx++) {
    const part = parts[idx];

    if (/^===\s*.+?\s*===$/.test(part)) {
      const title = part.replace(/===/g, "").trim();
      if (title.toUpperCase() === "CANDIDATE TITLE") {
        skipNextBody = true;
        continue;
      }
      nodes.push(
        <div key={`hdr-${idx}`} className="resume-section-header">
          <span>{title}</span>
        </div>
      );
      continue;
    }

    const lines = part.split("\n");
    const bodyLines = lines.filter((line) => !shouldSkipPreviewLine(line));
    if (!bodyLines.some((l) => l.trim())) continue;

    if (skipNextBody) {
      skipNextBody = false;
      const designation = bodyLines.map((l) => l.trim()).filter(Boolean).join(" ");
      if (designation) {
        nodes.push(
          <div key={`title-${idx}`} className="resume-designation-header">
            {designation}
          </div>
        );
      }
      continue;
    }

    nodes.push(
      <div key={`body-${idx}`} className="resume-section-body">
        {renderBodyLines(bodyLines, `body-${idx}`)}
      </div>
    );
  }

  return nodes;
}

function formatCategoryLabel(category) {
  if (!category) return "";
  return category
    .replace(/-/g, " ")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ResumePreview({ resumeData, category: categoryOverride }) {
  if (!resumeData) return null;

  const { resume_text = "", category: categoryFromData, pdf_url } = resumeData;

  const category = categoryFromData || categoryOverride || "";
  const downloadUrl = pdf_url ? getDownloadUrl(pdf_url) : null;

  if (!resume_text.trim()) {
    return (
      <div className="resume-preview">
        <p className="resume-empty">No resume content was returned.</p>
      </div>
    );
  }

  return (
    <div className="resume-preview">
      <div className="preview-header">
        <div className="preview-title-row">
          <div>
            <h2 className="preview-title">
              <FileText size={22} />
              Your Resume
            </h2>
            {category && (
              <p className="preview-category">{formatCategoryLabel(category)}</p>
            )}
          </div>
          {pdf_url && (
            <a
              id="download-pdf-btn"
              href={downloadUrl}
              download
              className="download-btn"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Download size={18} />
              Download PDF
            </a>
          )}
        </div>
      </div>

      <div className="resume-content">
        <div className="resume-paper">{formatResumeText(resume_text)}</div>
      </div>
    </div>
  );
}
