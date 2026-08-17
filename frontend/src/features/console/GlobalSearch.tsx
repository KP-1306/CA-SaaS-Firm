import type * as React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { list } from './api';
import type { Row } from './types';

type SearchTarget = 'clients' | 'team' | 'work' | 'services' | 'documents';

type SearchGroup = {
  key: SearchTarget;
  label: string;
  rows: Row[];
};

type SearchResult = {
  group: SearchTarget;
  groupLabel: string;
  id: string;
  title: string;
  subtitle: string;
  workItemId?: string;
};

function resultTitle(group: SearchTarget, row: Row): string {
  switch (group) {
    case 'clients':
      return String(row.trade_name || row.legal_name || 'Unnamed client');
    case 'team':
      return String(row.name || row.email || 'Unnamed employee');
    case 'work':
      return String(row.title || 'Untitled work item');
    case 'services':
      return String(row.name || 'Unnamed service');

    case 'documents':
      return String(
        row.original_name
        || row.name
        || 'Unnamed document'
      );
  }
}

function resultSubtitle(group: SearchTarget, row: Row): string {
  switch (group) {
    case 'clients':
      return [
        row.client_type,
        row.pan,
        row.engagement_status,
      ].filter(Boolean).join(' · ');

    case 'team':
      return [
        row.employee_code,
        row.email,
        row.role,
      ].filter(Boolean).join(' · ');

    case 'work':
      return [
        row.client_name,
        row.service_name,
        row.status,
      ].filter(Boolean).join(' · ');

    case 'services':
      return [
        row.code,
        row.domain_name,
        row.status,
      ].filter(Boolean).join(' · ');

    case 'documents':
      return [
        row.client_name,
        row.status,
        row.content_type,
        row.source,
      ].filter(Boolean).join(' · ');
  }
}

function resultWorkItemId(
  group: SearchTarget,
  row: Row,
): string | undefined {
  if (group === 'work') {
    const id = row.id;

    if (id === undefined || id === null || id === '') {
      return undefined;
    }

    return String(id);
  }

  const workItemId = row.work_item_id;

  if (
    workItemId === undefined
    || workItemId === null
    || workItemId === ''
  ) {
    return undefined;
  }

  return String(workItemId);
}


function normalizeSearchResult(
  group: SearchGroup,
  row: Row,
): SearchResult {
  const workItemId = resultWorkItemId(
    group.key,
    row,
  );

  const result: SearchResult = {
    group: group.key,
    groupLabel: group.label,
    id: String(
      row.id
      ?? `${group.key}-${resultTitle(group.key, row)}`
    ),
    title: resultTitle(
      group.key,
      row,
    ),
    subtitle: resultSubtitle(
      group.key,
      row,
    ),
  };

  if (workItemId !== undefined) {
    result.workItemId = workItemId;
  }

  return result;
}


export function GlobalSearch({
  onNavigate,
}: {
  onNavigate: (
    target: SearchTarget,
    id?: string,
    workItemId?: string,
  ) => void;
}): React.JSX.Element {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const [query, setQuery] = useState('');
  const [groups, setGroups] = useState<SearchGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);

  const trimmedQuery = query.trim();

  const results = useMemo<SearchResult[]>(
    () =>
      groups.flatMap(
        (group) =>
          group.rows.map(
            (row) =>
              normalizeSearchResult(
                group,
                row,
              ),
          ),
      ),
    [groups],
  );


  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent): void => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }

      if (event.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };

    document.addEventListener('keydown', handleShortcut);
    return () => document.removeEventListener('keydown', handleShortcut);
  }, []);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent): void => {
      if (
        wrapperRef.current
        && event.target instanceof Node
        && !wrapperRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  useEffect(() => {
    if (trimmedQuery.length < 3) {
      setGroups([]);
      setLoading(false);
      setError('');
      setActiveIndex(-1);
      return;
    }

    let cancelled = false;

    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');

      Promise.all([
        list('clients', { search: trimmedQuery }),
        list('employees', { search: trimmedQuery }),
        list('work-items', { search: trimmedQuery }),
        list('services', { search: trimmedQuery }),
        list('document-requests', { search: trimmedQuery }),
        list('document-attachments', { search: trimmedQuery }),
      ])
        .then(([
          clients,
          employees,
          work,
          services,
          documentRequests,
          documentAttachments,
        ]) => {
          if (cancelled) return;

          const documents = [
            ...documentRequests,
            ...documentAttachments,
          ].slice(0, 5);

          setGroups([
            { key: 'clients', label: 'Clients', rows: clients.slice(0, 5) },
            { key: 'team', label: 'Employees', rows: employees.slice(0, 5) },
            { key: 'work', label: 'Work', rows: work.slice(0, 5) },
            { key: 'services', label: 'Services', rows: services.slice(0, 5) },
            { key: 'documents', label: 'Documents', rows: documents },
          ]);

          setOpen(true);
          setActiveIndex(-1);
        })
        .catch((unknownError: unknown) => {
          if (cancelled) return;

          setGroups([]);
          setError(
            unknownError instanceof Error
              ? unknownError.message
              : 'Search could not be completed.',
          );
          setOpen(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [trimmedQuery]);

  const choose = (result: SearchResult): void => {
    onNavigate(
      result.group,
      result.id,
      result.workItemId,
    );
    setQuery('');
    setGroups([]);
    setOpen(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ): void => {
    if (!open && event.key === 'ArrowDown') {
      setOpen(true);
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();

      if (results.length > 0) {
        setActiveIndex((current) => (
          current >= results.length - 1 ? 0 : current + 1
        ));
      }
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();

      if (results.length > 0) {
        setActiveIndex((current) => (
          current <= 0 ? results.length - 1 : current - 1
        ));
      }
    }

    if (
      event.key === 'Enter'
      && activeIndex >= 0
      && results[activeIndex]
    ) {
      event.preventDefault();
      choose(results[activeIndex]);
    }

    if (event.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  let globalIndex = -1;

  return (
    <div className="cx-global-search" ref={wrapperRef}>
      <div className="cx-global-search-box">
        <span
          className="cx-global-search-icon"
          aria-hidden="true"
        >
          ⌕
        </span>

        <input
          ref={inputRef}
          type="search"
          value={query}
          placeholder="Search clients, employees, work, services or documents"
          aria-label="Global search"
          aria-expanded={open}
          aria-controls="cx-global-search-results"
          autoComplete="off"
          onFocus={() => {
            if (trimmedQuery.length >= 3) setOpen(true);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(-1);
          }}
          onKeyDown={handleKeyDown}
        />

        <span className="cx-global-search-shortcut">Ctrl K</span>
      </div>

      {open && trimmedQuery.length >= 3 ? (
        <div
          id="cx-global-search-results"
          className="cx-global-search-results"
          role="listbox"
        >
          <div className="cx-global-search-heading">
            <span>Search results</span>
            <span>{results.length} found</span>
          </div>

          {loading ? (
            <div className="cx-global-search-state">
              Searching…
            </div>
          ) : null}

          {!loading && error ? (
            <div className="cx-global-search-state danger">
              {error}
            </div>
          ) : null}

          {!loading && !error && results.length === 0 ? (
            <div className="cx-global-search-state">
              No matching records found.
            </div>
          ) : null}

          {!loading && !error
            ? groups.map((group) => {
              if (group.rows.length === 0) return null;

              return (
                <section
                  key={group.key}
                  className="cx-global-search-group"
                  aria-label={group.label}
                >
                  <div className="cx-global-search-group-title">
                    {group.label}
                  </div>

                  {group.rows.map((row) => {
                    globalIndex += 1;
                    const currentIndex = globalIndex;

                    const result = normalizeSearchResult(
                      group,
                      row,
                    );

                    return (
                      <button
                        key={`${result.group}-${result.id}`}
                        type="button"
                        role="option"
                        aria-selected={activeIndex === currentIndex}
                        className={
                          activeIndex === currentIndex
                            ? 'cx-global-search-result active'
                            : 'cx-global-search-result'
                        }
                        onMouseEnter={() => setActiveIndex(currentIndex)}
                        onClick={() => choose(result)}
                      >
                        <span className="cx-global-search-result-main">
                          <strong>{result.title}</strong>
                          {result.subtitle ? (
                            <small>{result.subtitle}</small>
                          ) : null}
                        </span>

                        <span className="cx-global-search-open">
                          Open
                        </span>
                      </button>
                    );
                  })}
                </section>
              );
            })
            : null}

          <div className="cx-global-search-footer">
            <span>↑ ↓ Navigate</span>
            <span>Enter Open</span>
            <span>Esc Close</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
