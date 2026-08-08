export interface HelpEntry {
  id: string;
  title: string;
  summary: string;

  purpose?: string;
  whoUses?: string;
  whoCanView?: string;
  whoCanEdit?: string;
  workflowImpact?: string;

  examples?: string[];
  commonMistakes?: string[];
  related?: string[];
}
