# Shared hooks

Neutral React hooks shared by the internal and portal planes.

Empty by design. Hooks that carry domain meaning belong to a feature under
`src/features/`; hooks that carry authentication state must not be shared
between planes at all (AR §2.4).

Owned by later work packages.
