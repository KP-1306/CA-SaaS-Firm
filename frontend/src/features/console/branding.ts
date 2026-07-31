import { useEffect, useState } from 'react';
import { getObject } from './api';

export interface BrandCapabilities {
  is_executive?: boolean;
  role?: string | null;
}

export interface Brand {
  firm_name: string;
  legal_name: string;
  source?: string;
  capabilities?: BrandCapabilities;
}

const DEFAULT_BRAND: Brand = { firm_name: 'Vridhi Consultants', legal_name: 'Vridhi Consultants', capabilities: { is_executive: false } };

// Central brand resolution: backend FirmProfile via /branding/, with a safe
// default. No component should hard-code the firm name.
export function useBrand(): Brand {
  const [brand, setBrand] = useState<Brand>(DEFAULT_BRAND);
  useEffect(() => {
    let active = true;
    getObject('branding')
      .then((row) => {
        if (!active) return;
        const b: Brand = {
          firm_name: String(row.firm_name ?? DEFAULT_BRAND.firm_name),
          legal_name: String(row.legal_name ?? row.firm_name ?? DEFAULT_BRAND.legal_name),
          ...(row.source ? { source: String(row.source) } : {}),
          capabilities: (row.capabilities as BrandCapabilities) ?? { is_executive: false },
        };
        setBrand(b);
        if (typeof document !== 'undefined') document.title = `${b.firm_name} - Operations Console`;
      })
      .catch(() => {
        /* keep default brand on error */
      });
    return () => {
      active = false;
    };
  }, []);
  return brand;
}
