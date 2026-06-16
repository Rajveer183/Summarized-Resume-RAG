/**
 * CategorySelector.jsx — Dropdown for selecting resume category.
 */
import { ChevronDown, Briefcase } from "lucide-react";

export default function CategorySelector({ categories, selected, onChange, disabled }) {
  const formatLabel = (cat) =>
    cat
      .replace(/-/g, " ")
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="selector-wrapper">
      <label className="selector-label">
        <Briefcase size={16} className="label-icon" />
        Select Resume Category
      </label>
      <div className="selector-container">
        <select
          id="category-select"
          className="category-select"
          value={selected}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || categories.length === 0}
        >
          <option value="">— Choose a Category —</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {formatLabel(cat)}
            </option>
          ))}
        </select>
        <ChevronDown size={18} className="select-arrow" />
      </div>
      {categories.length === 0 && (
        <p className="selector-hint">Loading categories...</p>
      )}
    </div>
  );
}
