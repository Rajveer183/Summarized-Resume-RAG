/**
 * App.jsx — Main application component.
 */
import { useState, useEffect } from "react";
import { getCategories, generateResume } from "./api/resumeApi";
import CategorySelector from "./components/CategorySelector";
import GenerateButton from "./components/GenerateButton";
import ResumePreview from "./components/ResumePreview";
import { AlertCircle, BarChart3, FileText } from "lucide-react";
import AccuracyDashboard from "./components/AccuracyDashboard";
import "./styles/App.css";

export default function App() {
  const [activeView, setActiveView] = useState("generator");
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [resumeData, setResumeData] = useState(null);
  const [error, setError] = useState("");
  const [catError, setCatError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const cats = await getCategories();
        setCategories(cats);
      } catch {
        setCatError(
          "Unable to connect to the server. Please try again in a moment."
        );
      }
    })();
  }, []);

  const handleGenerate = async () => {
    if (!selectedCategory) {
      setError("Please select a category before generating.");
      return;
    }
    setError("");
    setResumeData(null);
    setLoading(true);

    try {
      const result = await generateResume(selectedCategory);
      setResumeData(result);
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Resume generation failed. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="bg-orb orb-1" />
      <div className="bg-orb orb-2" />
      <div className="bg-orb orb-3" />

      <nav className="navbar">
        <div className="nav-brand">
          <FileText size={26} className="brand-icon" />
          <span className="brand-text">Resume Generator</span>
        </div>
        <div className="nav-pills">
          <button
            type="button"
            className={`nav-tab ${activeView === "generator" ? "active" : ""}`}
            onClick={() => setActiveView("generator")}
          >
            <FileText size={14} /> Generator
          </button>
          <button
            type="button"
            className={`nav-tab ${activeView === "accuracy" ? "active" : ""}`}
            onClick={() => setActiveView("accuracy")}
          >
            <BarChart3 size={14} /> Evaluation
          </button>
        </div>
      </nav>

      {activeView === "accuracy" ? (
        <main className="main-content accuracy-view">
          {catError && (
            <div className="error-banner backend-error">
              <AlertCircle size={18} />
              <div>
                <strong>Service Unavailable</strong>
                <p>{catError}</p>
              </div>
            </div>
          )}
          <AccuracyDashboard categories={categories} />
        </main>
      ) : (
        <main className="main-content">
          {catError && (
            <div className="error-banner backend-error">
              <AlertCircle size={18} />
              <div>
                <strong>Service Unavailable</strong>
                <p>{catError}</p>
              </div>
            </div>
          )}

          <header className="hero hero-compact">
            <h1 className="hero-title">Resume Generator</h1>
            <p className="hero-subtitle">
              Choose a professional category and create a tailored resume in
              seconds.
            </p>
          </header>

          <div className="control-panel glass-card">
            <div className="panel-header">
              <h2 className="panel-title">Create Your Resume</h2>
            </div>

            <div className="control-row">
              <CategorySelector
                categories={categories}
                selected={selectedCategory}
                onChange={(val) => {
                  setSelectedCategory(val);
                  setError("");
                  setResumeData(null);
                }}
                disabled={loading}
              />
              <GenerateButton
                onClick={handleGenerate}
                loading={loading}
                disabled={!selectedCategory || loading}
              />
            </div>

            {error && (
              <div className="error-banner inline-error">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {loading && (
              <div className="loading-progress">
                <div className="progress-bar">
                  <div className="progress-fill" />
                </div>
                <p className="loading-hint">Generating your resume…</p>
              </div>
            )}
          </div>

          {resumeData && (
            <ResumePreview resumeData={resumeData} category={selectedCategory} />
          )}
        </main>
      )}
    </div>
  );
}
