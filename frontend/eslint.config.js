import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ['./tsconfig.json', './tsconfig.node.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // The internal and portal planes must not import from one another.
      // Enforced structurally here; a boundary check owned by a later work
      // package will extend this to the backend contexts (AR §6.5).
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/apps/internal/**'],
              message:
                'The portal plane must not import from the internal plane (AR §2.4, ADR-004).',
            },
            {
              group: ['**/apps/portal/**'],
              message:
                'The internal plane must not import from the portal plane (AR §2.4, ADR-004).',
            },
          ],
        },
      ],
    },
  },
  prettierConfig,
  {
    // Neutral test code lives outside both planes and legitimately exercises
    // each plane's entry point in isolation. This override lets tests/ import
    // either plane; it does NOT let one plane import the other — the boundary
    // rule above still governs all of src/** (AR §2.4, ADR-004).
    files: ['tests/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
);
