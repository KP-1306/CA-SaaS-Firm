/**
 * Neutral bootstrap screen.
 *
 * Proves that an application entry point builds and renders. It shows the
 * application name, the plane and a bootstrap status, and nothing else.
 *
 * It contains no business feature, no mock user, no mock client and no fake
 * dashboard (EWP-000.1A §13). Domain screens are owned by later work packages.
 */

import type * as React from 'react';

import type { Plane } from '../plane';
import { planeLabel } from '../plane';
import { DEFAULT_BRAND_NAME } from '../brand';

export interface BootstrapScreenProps {
  readonly plane: Plane;
}

export function BootstrapScreen({ plane }: BootstrapScreenProps): React.JSX.Element {
  return (
    <main>
      <h1>{DEFAULT_BRAND_NAME}</h1>
      <p>{planeLabel(plane)}</p>
      <p>Bootstrap OK</p>
    </main>
  );
}
