/**
 * GenerateButton.jsx — Primary CTA button with loading state.
 */
import { Sparkles, Loader2 } from "lucide-react";

export default function GenerateButton({ onClick, loading, disabled }) {
  return (
    <button
      id="generate-resume-btn"
      className={`generate-btn ${loading ? "loading" : ""}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading ? (
        <>
          <Loader2 size={20} className="spin-icon" />
          <span>Generating Resume...</span>
          <span className="loading-dots">
            <span>.</span><span>.</span><span>.</span>
          </span>
        </>
      ) : (
        <>
          <Sparkles size={20} />
          <span>Generate Resume</span>
        </>
      )}
    </button>
  );
}
