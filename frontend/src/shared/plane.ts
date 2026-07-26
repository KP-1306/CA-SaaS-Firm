/**
 * Application plane identity.
 *
 * The internal and portal planes are structurally separate (AR §2.4, ADR-004):
 * separate entry points, separate bundles, separate authentication state.
 * This module carries only the neutral plane identifier — never shared session
 * or authentication state, which would defeat the separation.
 */

export const PLANES = ['internal', 'portal'] as const;

export type Plane = (typeof PLANES)[number];

export const PLANE_LABELS: Readonly<Record<Plane, string>> = {
  internal: 'Internal',
  portal: 'Client Portal',
};

export function planeLabel(plane: Plane): string {
  return PLANE_LABELS[plane];
}
