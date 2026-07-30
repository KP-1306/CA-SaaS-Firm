import type * as React from 'react';
import type { ReactNode } from 'react';
import { label } from './types';
import type { Row } from './types';

export function Chip({ value, tone }: { value: string; tone?: string }): React.JSX.Element {
  return <span className={`cx-chip ${tone ?? ''}`}>{label(value)}</span>;
}

export function Loading(): React.JSX.Element {
  return <div className="cx-loading">Loading...</div>;
}

export function Empty({ message }: { message: string }): React.JSX.Element {
  return <div className="cx-empty">{message}</div>;
}

export function ErrorBar({ error }: { error: string }): React.JSX.Element | null {
  if (!error) return null;
  return <div className="cx-error">{error}</div>;
}

export interface Column {
  key: string;
  header: string;
  render?: (row: Row) => ReactNode;
}

export function DataTable({
  columns,
  rows,
  onRow,
  empty,
}: {
  columns: Column[];
  rows: Row[];
  onRow?: (row: Row) => void;
  empty: string;
}): React.JSX.Element {
  if (rows.length === 0) return <Empty message={empty} />;
  return (
    <table className="cx-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row.id)} onClick={() => onRow?.(row)} style={{ cursor: onRow ? 'pointer' : 'default' }}>
            {columns.map((c) => (
              <td key={c.key}>{c.render ? c.render(row) : String(row[c.key] ?? '-')}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export interface Field {
  name: string;
  kind?: 'text' | 'textarea' | 'select' | 'date' | 'checkbox';
  options?: readonly string[];
  labels?: (v: string) => string;
}

export function Drawer({
  title,
  fields,
  value,
  onChange,
  onClose,
  onSave,
  extra,
}: {
  title: string;
  fields: Field[];
  value: Row;
  onChange: (next: Row) => void;
  onClose: () => void;
  onSave: () => void;
  extra?: ReactNode;
}): React.JSX.Element {
  return (
    <div className="cx-drawer-backdrop" onClick={onClose}>
      <div className="cx-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="cx-drawer-header">
          <h3>{title}</h3>
          <button type="button" className="cx-btn subtle cx-drawer-back" aria-label="Back" onClick={onClose}>
            ← Back
          </button>
        </div>
        {fields.map((f) => (
          <div className="cx-field" key={f.name}>
            <label>{label(f.name.replace(/_id$/, ''))}</label>
            {f.kind === 'textarea' ? (
              <textarea value={String(value[f.name] ?? '')} onChange={(e) => onChange({ ...value, [f.name]: e.target.value })} />
            ) : f.kind === 'select' ? (
              <select value={String(value[f.name] ?? '')} onChange={(e) => onChange({ ...value, [f.name]: e.target.value })}>
                <option value="">-</option>
                {(f.options ?? []).map((o) => (
                  <option key={o} value={o}>
                    {f.labels ? f.labels(o) : label(o)}
                  </option>
                ))}
              </select>
            ) : f.kind === 'checkbox' ? (
              <input
                type="checkbox"
                checked={Boolean(value[f.name])}
                onChange={(e) => onChange({ ...value, [f.name]: e.target.checked })}
              />
            ) : (
              <input
                type={f.kind === 'date' ? 'date' : 'text'}
                value={String(value[f.name] ?? '')}
                onChange={(e) => onChange({ ...value, [f.name]: e.target.value })}
              />
            )}
          </div>
        ))}
        {extra}
        <div className="cx-drawer-actions">
          <button type="button" className="cx-btn subtle" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="cx-btn" onClick={onSave}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
