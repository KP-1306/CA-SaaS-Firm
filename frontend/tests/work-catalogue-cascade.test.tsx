
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
  WorkCatalogueCascade,
} from '../src/features/console/work';


const verticals = [
  {
    id: 'vertical-loans',
    name: 'Loans',
    status: 'ACTIVE',
  },
  {
    id: 'vertical-tax',
    name: 'Accounts & Taxation',
    status: 'ACTIVE',
  },
];

const domains = [
  {
    id: 'domain-retail',
    vertical_id: 'vertical-loans',
    name: 'Retail Loans',
    status: 'ACTIVE',
  },
  {
    id: 'domain-business',
    vertical_id: 'vertical-loans',
    name: 'Business Loans',
    status: 'ACTIVE',
  },
  {
    id: 'domain-itr',
    vertical_id: 'vertical-tax',
    name: 'Income Tax',
    status: 'ACTIVE',
  },
];

const services = [
  {
    id: 'service-home',
    domain_id: 'domain-retail',
    name: 'Home Loan',
    status: 'ACTIVE',
  },
  {
    id: 'service-car',
    domain_id: 'domain-retail',
    name: 'Car Loan',
    status: 'ACTIVE',
  },
  {
    id: 'service-msme',
    domain_id: 'domain-business',
    name: 'MSME Loan',
    status: 'ACTIVE',
  },
  {
    id: 'service-itr',
    domain_id: 'domain-itr',
    name: 'ITR Filing',
    status: 'ACTIVE',
  },
];


function renderCascade(
  overrides: Record<string, unknown> = {},
) {
  const props = {
    verticalRows: verticals,
    domainRows: domains,
    serviceRows: services,
    selectedVerticalId: '',
    selectedDomainId: '',
    selectedServiceId: '',
    onVerticalChange: vi.fn(),
    onDomainChange: vi.fn(),
    onServiceChange: vi.fn(),
    ...overrides,
  };

  return {
    ...render(
      createElement(
        WorkCatalogueCascade,
        props,
      ),
    ),
    props,
  };
}


describe(
  'Vridhi work catalogue cascade',
  () => {
    it(
      'starts with Domain and Service disabled',
      () => {
        renderCascade();

        expect(
          screen.getByLabelText('Vertical'),
        ).toBeEnabled();

        expect(
          screen.getByLabelText('Domain'),
        ).toBeDisabled();

        expect(
          screen.getByLabelText('Service'),
        ).toBeDisabled();
      },
    );

    it(
      'returns the selected Vertical',
      () => {
        const { props } = renderCascade();

        fireEvent.change(
          screen.getByLabelText('Vertical'),
          {
            target: {
              value: 'vertical-loans',
            },
          },
        );

        expect(
          props.onVerticalChange,
        ).toHaveBeenCalledWith(
          'vertical-loans',
        );
      },
    );

    it(
      'shows only Domains belonging to the selected Vertical',
      () => {
        renderCascade({
          selectedVerticalId:
            'vertical-loans',
        });

        const domain =
          screen.getByLabelText('Domain');

        expect(domain).toBeEnabled();

        expect(
          screen.getByRole(
            'option',
            { name: 'Retail Loans' },
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByRole(
            'option',
            { name: 'Income Tax' },
          ),
        ).not.toBeInTheDocument();
      },
    );

    it(
      'shows only Services belonging to the selected Domain',
      () => {
        renderCascade({
          selectedVerticalId:
            'vertical-loans',
          selectedDomainId:
            'domain-retail',
        });

        const service =
          screen.getByLabelText('Service');

        expect(service).toBeEnabled();

        expect(
          screen.getByRole(
            'option',
            { name: 'Home Loan' },
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByRole(
            'option',
            { name: 'Car Loan' },
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByRole(
            'option',
            { name: 'MSME Loan' },
          ),
        ).not.toBeInTheDocument();
      },
    );

    it(
      'returns the selected Domain and Service',
      () => {
        const onDomainChange = vi.fn();
        const onServiceChange = vi.fn();

        const view = renderCascade({
          selectedVerticalId:
            'vertical-loans',
          onDomainChange,
          onServiceChange,
        });

        fireEvent.change(
          screen.getByLabelText('Domain'),
          {
            target: {
              value: 'domain-retail',
            },
          },
        );

        expect(
          onDomainChange,
        ).toHaveBeenCalledWith(
          'domain-retail',
        );

        view.rerender(
          createElement(
            WorkCatalogueCascade,
            {
              verticalRows: verticals,
              domainRows: domains,
              serviceRows: services,
              selectedVerticalId:
                'vertical-loans',
              selectedDomainId:
                'domain-retail',
              selectedServiceId: '',
              onVerticalChange: vi.fn(),
              onDomainChange,
              onServiceChange,
            },
          ),
        );

        fireEvent.change(
          screen.getByLabelText('Service'),
          {
            target: {
              value: 'service-home',
            },
          },
        );

        expect(
          onServiceChange,
        ).toHaveBeenCalledWith(
          'service-home',
        );
      },
    );

    it(
      'preserves an inactive existing selection while editing',
      () => {
        renderCascade({
          verticalRows: [
            ...verticals,
            {
              id: 'vertical-old',
              name: 'Legacy Vertical',
              status: 'INACTIVE',
            },
          ],
          domainRows: [
            ...domains,
            {
              id: 'domain-old',
              vertical_id: 'vertical-old',
              name: 'Legacy Domain',
              status: 'INACTIVE',
            },
          ],
          serviceRows: [
            ...services,
            {
              id: 'service-old',
              domain_id: 'domain-old',
              name: 'Legacy Service',
              status: 'INACTIVE',
            },
          ],
          selectedVerticalId:
            'vertical-old',
          selectedDomainId:
            'domain-old',
          selectedServiceId:
            'service-old',
        });

        expect(
          screen.getByLabelText('Vertical'),
        ).toHaveValue('vertical-old');

        expect(
          screen.getByLabelText('Domain'),
        ).toHaveValue('domain-old');

        expect(
          screen.getByLabelText('Service'),
        ).toHaveValue('service-old');
      },
    );
  },
);
