import type * as React from 'react';

type Props = {
  expanded: boolean;
  controls: string;
  onClick: () => void;
};

export default function HelpIcon({
  expanded,
  controls,
  onClick,
}: Props): React.JSX.Element {
  return (
    <button
      type="button"
      className="cx-help-icon"
      aria-label="Help"
      aria-expanded={expanded}
      aria-controls={controls}
      onClick={onClick}
    >
      ?
    </button>
  );
}
