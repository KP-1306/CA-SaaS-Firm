import type * as React from 'react';

import type { HelpEntry } from '../../help/types';

type Props = {
  help: HelpEntry;
  id: string;
};

function HelpSection({
  title,
  value,
}: {
  title: string;
  value: string | undefined;
}): React.JSX.Element | null {
  if (!value) return null;

  return (
    <section className="cx-help-popover-section">
      <strong>{title}</strong>
      <p>{value}</p>
    </section>
  );
}

function HelpList({
  title,
  values,
}: {
  title: string;
  values: string[] | undefined;
}): React.JSX.Element | null {
  if (!values || values.length === 0) return null;

  return (
    <section className="cx-help-popover-section">
      <strong>{title}</strong>

      <ul className="cx-help-list">
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </section>
  );
}

export default function HelpPopover({
  help,
  id,
}: Props): React.JSX.Element {
  return (
    <div
      id={id}
      className="cx-help-popover"
      role="dialog"
      aria-label={`${help.title} help`}
    >
      <div className="cx-help-popover-header">
        <span className="cx-help-popover-kicker">
          Contextual help
        </span>

        <h3>{help.title}</h3>

        <p className="cx-help-summary">
          {help.summary}
        </p>
      </div>

      <HelpSection
        title="Purpose"
        value={help.purpose}
      />

      <HelpSection
        title="Who uses this"
        value={help.whoUses}
      />

      <div className="cx-help-access">
        <HelpSection
          title="View access"
          value={help.whoCanView}
        />

        <HelpSection
          title="Edit access"
          value={help.whoCanEdit}
        />
      </div>

      <HelpSection
        title="Workflow impact"
        value={help.workflowImpact}
      />

      <HelpList
        title="Examples"
        values={help.examples}
      />

      <HelpList
        title="Common mistakes"
        values={help.commonMistakes}
      />

      <HelpList
        title="Related topics"
        values={help.related}
      />
    </div>
  );
}
