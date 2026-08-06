
import { createElement } from 'react';
import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  OperationalFieldsPanel,
  checklistVisualState,
  type ServiceOperationalFieldDefinition,
} from '../src/features/console/work';


const definitions:
  ServiceOperationalFieldDefinition[] = [
    {
      id: 'field-applicant',
      service_id: 'home-loan',
      key: 'applicant_type',
      label: 'Applicant Type',
      field_type: 'SELECT',
      required: true,
      options: [
        'Salaried',
        'Self-employed',
      ],
      display_order: 10,
      is_active: true,
    },
    {
      id: 'field-amount',
      service_id: 'home-loan',
      key: 'loan_amount',
      label: 'Loan Amount',
      field_type: 'NUMBER',
      required: true,
      display_order: 20,
      is_active: true,
    },
    {
      id: 'field-notes',
      service_id: 'home-loan',
      key: 'property_notes',
      label: 'Property Notes',
      field_type: 'LONG_TEXT',
      display_order: 30,
      is_active: true,
    },
  ];


describe(
  'Vridhi operational work UI',
  () => {
    it(
      'renders configured fields',
      () => {
        render(
          createElement(
            OperationalFieldsPanel,
            {
              definitions,
              values: {},
              onChange: vi.fn(),
            },
          ),
        );

        expect(
          screen.getByLabelText(
            /Applicant Type/,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByLabelText(
            /Loan Amount/,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByLabelText(
            'Property Notes',
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      'returns changes by field key',
      () => {
        const onChange = vi.fn();

        render(
          createElement(
            OperationalFieldsPanel,
            {
              definitions,
              values: {},
              onChange,
            },
          ),
        );

        fireEvent.change(
          screen.getByLabelText(
            /Applicant Type/,
          ),
          {
            target: {
              value: 'Salaried',
            },
          },
        );

        expect(
          onChange,
        ).toHaveBeenCalledWith(
          'applicant_type',
          'Salaried',
        );
      },
    );

    it(
      'renders existing values',
      () => {
        render(
          createElement(
            OperationalFieldsPanel,
            {
              definitions,
              values: {
                applicant_type:
                  'Self-employed',
                loan_amount:
                  2500000,
              },
              onChange: vi.fn(),
            },
          ),
        );

        expect(
          screen.getByLabelText(
            /Applicant Type/,
          ),
        ).toHaveValue(
          'Self-employed',
        );

        expect(
          screen.getByLabelText(
            /Loan Amount/,
          ),
        ).toHaveValue(
          2500000,
        );
      },
    );

    it(
      'shows missing status',
      () => {
        expect(
          checklistVisualState({
            status: 'REQUESTED',
            attachment_count: 0,
            accepted_attachment_count: 0,
            pending_review_count: 0,
          }),
        ).toEqual({
          key: 'MISSING',
          label:
            'Required document missing',
          tone: 'missing',
        });
      },
    );

    it(
      'shows pending review status',
      () => {
        expect(
          checklistVisualState({
            status: 'RECEIVED',
            attachment_count: 1,
            accepted_attachment_count: 0,
            pending_review_count: 1,
          }).key,
        ).toBe(
          'PENDING_REVIEW',
        );
      },
    );

    it(
      'shows green accepted status',
      () => {
        expect(
          checklistVisualState({
            status: 'ACCEPTED',
            attachment_count: 1,
            accepted_attachment_count: 1,
            pending_review_count: 0,
          }),
        ).toEqual({
          key: 'RECEIVED',
          label:
            'Received and accepted',
          tone: 'received',
        });
      },
    );

    it(
      'shows rejected status',
      () => {
        expect(
          checklistVisualState({
            status: 'REJECTED',
            attachment_count: 1,
            accepted_attachment_count: 0,
            pending_review_count: 0,
          }).key,
        ).toBe(
          'REJECTED',
        );
      },
    );
  },
);
