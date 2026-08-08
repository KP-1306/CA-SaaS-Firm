import type * as React from 'react';

import Help from './Help';

type GuidedLabelProps = {
  title: React.ReactNode;
  help: string;
};

export function GuidedLabel({
  title,
  help,
}: GuidedLabelProps): React.JSX.Element {
  return (
    <span className="cx-guided-label">
      <span>{title}</span>
      <Help topic={help} />
    </span>
  );
}

type GuidedTitleProps = GuidedLabelProps & {
  className?: string;
};

export function PageTitle({
  title,
  help,
  className,
}: GuidedTitleProps): React.JSX.Element {
  return (
    <div className="cx-guided-heading">
      <h1 className={className}>{title}</h1>
      <Help topic={help} />
    </div>
  );
}

export function SectionTitle({
  title,
  help,
  className,
}: GuidedTitleProps): React.JSX.Element {
  return (
    <div className="cx-guided-heading">
      <h3 className={className}>{title}</h3>
      <Help topic={help} />
    </div>
  );
}

type FieldLabelProps = {
  label: React.ReactNode;
  help: string;
  className?: string;
};

export function FieldLabel({
  label,
  help,
  className,
}: FieldLabelProps): React.JSX.Element {
  return (
    <span className={className}>
      <span className="cx-guided-label">
        <span>{label}</span>
        <Help topic={help} />
      </span>
    </span>
  );
}
