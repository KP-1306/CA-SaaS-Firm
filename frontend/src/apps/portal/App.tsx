/**
 * Portal plane application root.
 *
 * Serves client organisations. Must never import from the internal plane
 * (AR §2.4, ADR-004), and must never share authentication state with it.
 * Routing, authentication and domain features are owned by later work packages.
 */

import type * as React from 'react';

import { BootstrapScreen } from '@shared/components/BootstrapScreen';

export function App(): React.JSX.Element {
  return <BootstrapScreen plane="portal" />;
}
