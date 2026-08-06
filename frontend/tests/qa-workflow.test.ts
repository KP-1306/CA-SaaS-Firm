import { describe, expect, it } from 'vitest';

import { buildQaResponses, qaTone } from '../src/features/console/qa';

describe('Phase 2C QA UI helpers', () => {
  it('builds preparer response payloads', () => {
    const result = buildQaResponses(
      [{
        id: 'response-1',
        preparer_response: 'YES',
        preparer_comment: 'Verified',
      }],
      'preparer',
    );

    expect(result).toEqual([{
      id: 'response-1',
      value: 'YES',
      comment: 'Verified',
      evidence_attachment_id: null,
    }]);
  });

  it('builds reviewer response payloads', () => {
    const result = buildQaResponses(
      [{
        id: 'response-2',
        reviewer_response: 'NO',
        reviewer_comment: 'Correction required',
      }],
      'reviewer',
    );

    expect(result[0]?.value).toBe('NO');
    expect(result[0]?.comment).toBe('Correction required');
  });

  it('maps QA states to stable tones', () => {
    expect(qaTone('APPROVED')).toBe('ok');
    expect(qaTone('OPEN')).toBe('danger');
    expect(qaTone('PENDING')).toBe('warn');
  });
});
