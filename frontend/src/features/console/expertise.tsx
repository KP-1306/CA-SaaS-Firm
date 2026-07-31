import type * as React from 'react';
import { useEffect, useState } from 'react';
import { list, remove, save } from './api';
import type { Row } from './types';
import { Chip, ErrorBar, Loading } from './ui';

const CATEGORIES = [
  'GST', 'INCOME_TAX', 'TDS', 'ROC', 'STATUTORY_AUDIT', 'INTERNAL_AUDIT', 'TAX_AUDIT',
  'BANK_AUDIT', 'CONCURRENT_AUDIT', 'ACCOUNTING', 'BOOKKEEPING', 'PAYROLL', 'COMPLIANCE',
  'COMPANY_FORMATION', 'PROJECT_FINANCE', 'MSME', 'FEMA', 'INTERNATIONAL_TAX',
  'NRI_TAXATION', 'TRANSFER_PRICING',
] as const;

const LEVELS = ['BASIC', 'INTERMEDIATE', 'ADVANCED', 'EXPERT'] as const;

function label(v: string): string {
  return v.split('_').map((w) => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');
}

export function ExpertisePanel({ employeeId }: { employeeId: string }): React.JSX.Element {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState<string>(CATEGORIES[0]);
  const [proficiency, setProficiency] = useState<string>('INTERMEDIATE');

  const load = (): void => {
    setLoading(true);
    list('employee-expertise', { employee_id: employeeId })
      .then((r) => {
        setRows(r);
        setError('');
      })
      .catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, [employeeId]);

  const add = (): void => {
    save('employee-expertise', { employee_id: employeeId, category, proficiency })
      .then(() => load())
      .catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)));
  };
  const del = (id: string): void => {
    remove('employee-expertise', id).then(() => load()).catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)));
  };
  const changeLevel = (row: Row, level: string): void => {
    save('employee-expertise', { id: row.id, proficiency: level }).then(() => load()).catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)));
  };

  const existing = new Set(rows.map((r) => String(r.category)));

  return (
    <div>
      <div className="cx-subhead"><h4>Expertise</h4></div>
      <ErrorBar error={error} />
      {loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <p style={{ color: '#64748b', fontSize: 13 }}>No expertise recorded.</p>
      ) : (
        <table className="cx-table">
          <thead><tr><th>Area</th><th>Proficiency</th><th></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.id)}>
                <td><Chip value={String(r.category_label ?? label(String(r.category)))} /></td>
                <td>
                  <select value={String(r.proficiency)} onChange={(e) => changeLevel(r, e.target.value)}>
                    {LEVELS.map((l) => <option key={l} value={l}>{label(l)}</option>)}
                  </select>
                </td>
                <td><button className="cx-btn subtle" onClick={() => del(String(r.id))}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="cx-toolbar" style={{ marginTop: 10 }}>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.filter((c) => !existing.has(c)).map((c) => <option key={c} value={c}>{label(c)}</option>)}
        </select>
        <select value={proficiency} onChange={(e) => setProficiency(e.target.value)}>
          {LEVELS.map((l) => <option key={l} value={l}>{label(l)}</option>)}
        </select>
        <button className="cx-btn" onClick={add} disabled={existing.has(category)}>Add expertise</button>
      </div>
    </div>
  );
}
