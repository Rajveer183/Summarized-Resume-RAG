/**
 * AccuracyDashboard — evaluation scores for one category or all categories.
 */
import { useState, useEffect, useCallback } from "react";
import {
  evaluateCategory,
  evaluateAll,
  getCachedAllAccuracyReport,
} from "../api/resumeApi";
import {
  BarChart3,
  RefreshCw,
  AlertCircle,
  FileCheck,
  Search,
  Layers,
  Shield,
} from "lucide-react";

const ALL_CATEGORIES_KEY = "__ALL__";

const METRIC_LABELS = {
  retrieval_accuracy: "Relevance",
  category_accuracy: "Category Match",
  content_accuracy: "Content Quality",
  privacy_accuracy: "Privacy",
};

function parsePercent(value) {
  if (value == null) return 0;
  return parseFloat(String(value).replace("%", "")) || 0;
}

function overallScore(row) {
  if (row?.overall_accuracy) return row.overall_accuracy;
  const score =
    parsePercent(row?.retrieval_accuracy) * 0.3 +
    parsePercent(row?.category_accuracy) * 0.25 +
    parsePercent(row?.content_accuracy) * 0.3 +
    parsePercent(row?.privacy_accuracy) * 0.15;
  return `${score.toFixed(1)}%`;
}

function AccuracyCard({ title, value, icon: Icon }) {
  const pct = parsePercent(value);

  return (
    <div className="accuracy-card glass-card">
      <div className="accuracy-card-header">
        <div className="accuracy-icon-wrap">{Icon && <Icon size={20} />}</div>
        <span className="accuracy-card-title">{title}</span>
      </div>
      <div className="accuracy-value">{value ?? "—"}</div>
      <div className="accuracy-progress-track">
        <div
          className="accuracy-progress-fill met"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

function PercentCell({ value }) {
  const pct = parsePercent(value);

  return (
    <td>
      <span className="cell-pct">{value ?? "—"}</span>
      <div className="cell-bar-track">
        <div
          className="cell-bar-fill met"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </td>
  );
}

function AllCategoriesTable({ rows }) {
  const valid = rows.filter((r) => !r.error && r.retrieval_accuracy);

  const avg = (key) => {
    if (!valid.length) return "—";
    const sum = valid.reduce((a, r) => a + parsePercent(r[key]), 0);
    return `${(sum / valid.length).toFixed(1)}%`;
  };

  const avgOverall = () => {
    if (!valid.length) return "—";
    const sum = valid.reduce((a, r) => a + parsePercent(overallScore(r)), 0);
    return `${(sum / valid.length).toFixed(1)}%`;
  };

  return (
    <div className="accuracy-all-table-wrap glass-card">
      <h3 className="all-table-title">All Categories</h3>
      <div className="accuracy-table-scroll">
        <table className="accuracy-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>{METRIC_LABELS.retrieval_accuracy}</th>
              <th>{METRIC_LABELS.category_accuracy}</th>
              <th>{METRIC_LABELS.content_accuracy}</th>
              <th>{METRIC_LABELS.privacy_accuracy}</th>
              <th>Overall</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.category} className={row.error ? "row-error" : ""}>
                <td className="cat-name">{row.category?.replace(/-/g, " ")}</td>
                {row.error ? (
                  <td colSpan={5} className="error-cell">
                    {row.error}
                  </td>
                ) : (
                  <>
                    <PercentCell value={row.retrieval_accuracy} />
                    <PercentCell value={row.category_accuracy} />
                    <PercentCell value={row.content_accuracy} />
                    <PercentCell value={row.privacy_accuracy} />
                    <PercentCell value={overallScore(row)} />
                  </>
                )}
              </tr>
            ))}
            {valid.length > 0 && (
              <tr className="row-average">
                <td className="cat-name">Average</td>
                <PercentCell value={avg("retrieval_accuracy")} />
                <PercentCell value={avg("category_accuracy")} />
                <PercentCell value={avg("content_accuracy")} />
                <PercentCell value={avg("privacy_accuracy")} />
                <PercentCell value={avgOverall()} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AccuracyDashboard({ categories = [] }) {
  const [selectedCategory, setSelectedCategory] = useState("");
  const [singleReport, setSingleReport] = useState(null);
  const [allRows, setAllRows] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isAllMode = selectedCategory === ALL_CATEGORIES_KEY;

  const loadAllReport = useCallback(async () => {
    setError("");
    try {
      const data = await getCachedAllAccuracyReport();
      setAllRows(data.categories || []);
    } catch (err) {
      if (err?.response?.status !== 404) {
        setError(err?.response?.data?.detail || err?.message);
      }
      setAllRows(null);
    }
  }, []);

  useEffect(() => {
    if (isAllMode) {
      loadAllReport();
    }
  }, [isAllMode, loadAllReport]);

  const runEvaluation = async () => {
    if (!selectedCategory) {
      setError("Please select a category.");
      return;
    }

    setLoading(true);
    setError("");

    if (!isAllMode) {
      setSingleReport(null);
    }

    try {
      if (isAllMode) {
        const data = await evaluateAll(false);
        setAllRows(data.categories || []);
      } else {
        const data = await evaluateCategory(selectedCategory, false, false);
        setSingleReport(data);
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Evaluation could not be completed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="accuracy-dashboard">
      <div className="panel-header">
        <h2 className="panel-title">
          <BarChart3 size={22} className="inline-icon" />
          Resume Evaluation
        </h2>
        <p className="panel-subtitle">
          {isAllMode
            ? "Compare quality scores across all categories."
            : "Review how well the generated resume fits the selected category."}
        </p>
      </div>

      <div className="accuracy-controls glass-card">
        <div className="control-row">
          <select
            className="category-select"
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              setError("");
              if (e.target.value !== ALL_CATEGORIES_KEY) {
                setAllRows(null);
                setSingleReport(null);
              }
            }}
            disabled={loading}
          >
            <option value="">Select category…</option>
            <option value={ALL_CATEGORIES_KEY}>All Categories (24)</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace(/-/g, " ")}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-secondary"
            onClick={runEvaluation}
            disabled={loading || !selectedCategory}
          >
            {loading ? (
              <RefreshCw size={16} className="spin" />
            ) : (
              <BarChart3 size={16} />
            )}
            Run Evaluation
          </button>
        </div>
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
          <p className="loading-hint">
            {isAllMode ? "Evaluating all categories…" : "Running evaluation…"}
          </p>
        </div>
      )}

      {!loading && allRows && allRows.length > 0 && isAllMode && (
        <AllCategoriesTable rows={allRows} />
      )}

      {!loading && singleReport && !isAllMode && !singleReport.error && (
        <div className="accuracy-report">
          <div className="accuracy-category-banner glass-card">
            <span className="accuracy-category-label">Category</span>
            <span className="accuracy-category-name">
              {singleReport.category?.replace(/-/g, " ")}
            </span>
          </div>

          <div className="accuracy-grid accuracy-grid-four">
            <AccuracyCard
              title={METRIC_LABELS.retrieval_accuracy}
              value={singleReport.retrieval_accuracy}
              icon={Search}
            />
            <AccuracyCard
              title={METRIC_LABELS.category_accuracy}
              value={singleReport.category_accuracy}
              icon={Layers}
            />
            <AccuracyCard
              title={METRIC_LABELS.content_accuracy}
              value={singleReport.content_accuracy}
              icon={FileCheck}
            />
            <AccuracyCard
              title={METRIC_LABELS.privacy_accuracy}
              value={singleReport.privacy_accuracy}
              icon={Shield}
            />
          </div>

          <div className="overall-accuracy-card glass-card">
            <div className="overall-label">Overall Score</div>
            <div className="overall-value">{overallScore(singleReport)}</div>
            <div className="accuracy-progress-track overall-track">
              <div
                className="accuracy-progress-fill overall-fill met"
                style={{
                  width: `${Math.min(parsePercent(overallScore(singleReport)), 100)}%`,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {!loading && singleReport?.error && (
        <div className="error-banner inline-error">
          <AlertCircle size={16} />
          <span>{singleReport.error}</span>
        </div>
      )}

      {!loading && isAllMode && !allRows?.length && !error && (
        <div className="cache-empty-hint glass-card">
          <p>
            No evaluation report yet. Select <strong>All Categories (24)</strong>{" "}
            and click <strong>Run Evaluation</strong>.
          </p>
        </div>
      )}
    </div>
  );
}
