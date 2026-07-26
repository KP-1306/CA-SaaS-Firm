/**
 * Internal plane application root.
 *
 * Serves firm staff. Must never import from the portal plane (AR §2.4).
 * Routing, authentication and domain features are owned by later work packages.
 */

import type * as React from 'react';

import { BootstrapScreen } from '@shared/components/BootstrapScreen';

export function App(): React.JSX.Element {
  return <BootstrapScreen plane="internal" />;
}
