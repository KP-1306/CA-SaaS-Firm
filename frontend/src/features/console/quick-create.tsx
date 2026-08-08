import type * as React from 'react';
import { useState } from 'react';


export type QuickCreateAction =
  | 'NEW_CLIENT'
  | 'NEW_WORK'
  | 'ASSIGN_WORK'
  | 'UPLOAD_CLIENT_DOCUMENT';


export function QuickCreateMenu({
  canAssign,
  onSelect,
}: {
  canAssign: boolean;
  onSelect: (action: QuickCreateAction) => void;
}): React.JSX.Element {
  const [open, setOpen] = useState(false);

  const choose = (action: QuickCreateAction): void => {
    setOpen(false);
    onSelect(action);
  };

  return (
    <div className="cx-quick-create">
      <button
        type="button"
        className="cx-btn cx-quick-create-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        + Create
      </button>

      {open ? (
        <div
          className="cx-quick-create-menu"
          role="menu"
          aria-label="Quick Create"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => choose('NEW_CLIENT')}
          >
            <strong>New Client</strong>
            <span>Open existing client creation</span>
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => choose('NEW_WORK')}
          >
            <strong>New Work Item</strong>
            <span>Open existing Work creation</span>
          </button>

          {canAssign ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => choose('ASSIGN_WORK')}
            >
              <strong>Assign Existing Work</strong>
              <span>Open existing assignment workspace</span>
            </button>
          ) : null}

          <button
            type="button"
            role="menuitem"
            onClick={() =>
              choose('UPLOAD_CLIENT_DOCUMENT')
            }
          >
            <strong>Upload Client Document</strong>
            <span>Select Work, then use existing Documents</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
