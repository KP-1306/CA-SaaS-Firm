import type * as React from 'react';

import Help from './Help';

type Props = {
  page: string;
};

export default function PageHelp({
  page,
}: Props): React.JSX.Element {
  return <Help topic={`page.${page}`} />;
}
