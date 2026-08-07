"use strict";

const {
  fs,
  path,
  parse,
  walk,
  namedFunction,
  directVariable,
  importDeclaration,
  namedImportBindings,
  findJsxByClass,
  findJsxElement,
  applyEdits,
  insertAt,
  assertSingleText,
  detectNewline,
  writePreservingNewline,
  ts,
} = require("./framework.cjs");


function indentBlock(
  text,
  newline
) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\n/g, newline);
}


function patchWorkFile(
  filePath,
  write
) {
  const original =
    fs.readFileSync(
      filePath,
      "utf8"
    );

  const newline =
    detectNewline(original);

  const sourceFile =
    parse(
      filePath,
      original
    );

  const edits = [];

  // ==========================================================
  // IMPORT: ./api -> add getObject
  // ==========================================================

  const apiImport =
    importDeclaration(
      sourceFile,
      "./api"
    );

  const namedImports =
    namedImportBindings(apiImport);

  const importNames =
    namedImports.elements.map(
      (element) =>
        element.name.text
    );

  if (
    importNames.includes("getObject")
  ) {
    throw new Error(
      "getObject is already imported. " +
      "Phase 4A.2 appears partially installed."
    );
  }

  const closingBrace =
    namedImports.end - 1;

  const namedImportText =
    original.slice(
      namedImports.pos,
      namedImports.end
    );

  const importInsertion =
    namedImportText.includes("\n") ||
    namedImportText.includes("\r")
      ? `  getObject,${newline}`
      : ", getObject";

  insertAt(
    edits,
    closingBrace,
    importInsertion,
    "api.getObject import"
  );

  // ==========================================================
  // COMPONENT: insert before statusTone
  // ==========================================================

  const statusTone =
    namedFunction(
      sourceFile,
      "statusTone"
    );

  const healthComponent = `
export type WorkHealthSnapshot = {
  contract_version: number;
  work_item_id: string;
  progress: number;
  health: 'GREEN' | 'AMBER' | 'RED';
  risk: 'LOW' | 'MEDIUM' | 'HIGH';
  current_controller:
    | 'OWNER'
    | 'CLIENT'
    | 'REVIEWER'
    | 'NONE';
  waiting_days: number;
  waiting_since: string | null;
  due_state:
    | 'ON_TRACK'
    | 'DUE_SOON'
    | 'OVERDUE';
  days_to_due: number | null;
  operational: {
    total: number;
    completed: number;
    remaining: number;
    mandatory_total: number;
    mandatory_completed: number;
    mandatory_remaining: number;
    completion_percent: number | null;
  };
  documents: {
    total: number;
    satisfied: number;
    pending: number;
    mandatory_total: number;
    mandatory_satisfied: number;
    mandatory_missing: number;
    missing: number;
    pending_review: number;
    rejected: number;
    expired: number;
    pending_acceptance: number;
    ready_for_review: boolean;
    readiness_state: string;
    health_score: number;
    blockers: Row[];
  };
  next_action: {
    code: string;
    label: string;
  };
  reasons: string[];
  calculated_at: string;
};

export function workHealthTone(
  health: unknown,
): 'stable' | 'watch' | 'risk' {
  if (health === 'RED') return 'risk';
  if (health === 'AMBER') return 'watch';
  return 'stable';
}

function dueStateText(
  state: WorkHealthSnapshot['due_state'],
  daysToDue: number | null,
): string {
  if (state === 'OVERDUE') {
    const days =
      typeof daysToDue === 'number'
        ? Math.abs(daysToDue)
        : null;

    if (days === null) return 'Overdue';

    return \`Overdue by \${days} day\${
      days === 1 ? '' : 's'
    }\`;
  }

  if (state === 'DUE_SOON') {
    if (daysToDue === 0) {
      return 'Due today';
    }

    if (
      typeof daysToDue === 'number'
    ) {
      return \`Due in \${daysToDue} day\${
        daysToDue === 1 ? '' : 's'
      }\`;
    }

    return 'Due soon';
  }

  if (
    typeof daysToDue === 'number'
  ) {
    return \`Due in \${daysToDue} day\${
      daysToDue === 1 ? '' : 's'
    }\`;
  }

  return 'On track';
}

export function WorkHealthCard({
  health,
  loading = false,
  error = '',
}: {
  health: WorkHealthSnapshot | null;
  loading?: boolean;
  error?: string;
}): React.JSX.Element {
  if (loading) {
    return (
      <section
        className="cx-work-health-shell loading"
        aria-label="Work health"
      >
        <span className="cx-work-health-kicker">
          Work health
        </span>
        <strong>
          Calculating operational health…
        </strong>
      </section>
    );
  }

  if (!health) {
    return (
      <section
        className="cx-work-health-shell unavailable"
        aria-label="Work health"
      >
        <span className="cx-work-health-kicker">
          Work health
        </span>
        <strong>
          Health unavailable
        </strong>
        <span>
          {error ||
            'Operational health could not be loaded.'}
        </span>
      </section>
    );
  }

  const tone =
    workHealthTone(
      health.health
    );

  const progress =
    Math.max(
      0,
      Math.min(
        100,
        Number(
          health.progress || 0
        ),
      ),
    );

  return (
    <section
      className={
        \`cx-work-health-shell \${tone}\`
      }
      aria-label="Work health"
      data-health={health.health}
    >
      <div className="cx-work-health-main">
        <div
          className="cx-work-health-progress"
          aria-label={
            \`\${progress}% complete\`
          }
        >
          <strong>
            {progress}%
          </strong>
          <span>complete</span>
        </div>

        <div className="cx-work-health-status">
          <span className="cx-work-health-kicker">
            Work health
          </span>

          <div className="cx-work-health-status-line">
            <strong>
              {label(health.health)}
            </strong>
            <span>·</span>
            <span>
              {label(health.risk)} risk
            </span>
          </div>

          <div
            className="cx-work-health-progress-track"
            aria-hidden="true"
          >
            <span
              style={{
                width:
                  \`\${progress}%\`,
              }}
            />
          </div>
        </div>
      </div>

      <div className="cx-work-health-metrics">
        <div>
          <span>
            Waiting on
          </span>
          <strong>
            {
              health.current_controller ===
              'NONE'
                ? 'No one'
                : label(
                    health.current_controller,
                  )
            }
          </strong>
          <small>
            {
              health.waiting_days > 0
                ? \`\${health.waiting_days} day\${
                    health.waiting_days === 1
                      ? ''
                      : 's'
                  }\`
                : 'No active wait'
            }
          </small>
        </div>

        <div>
          <span>Due</span>
          <strong>
            {label(
              health.due_state
            )}
          </strong>
          <small>
            {dueStateText(
              health.due_state,
              health.days_to_due,
            )}
          </small>
        </div>

        <div>
          <span>
            Work details
          </span>
          <strong>
            {
              health.operational
                .completed
            }/
            {
              health.operational
                .total
            }
          </strong>
          <small>
            {
              health.operational
                .mandatory_remaining
            } mandatory remaining
          </small>
        </div>

        <div>
          <span>
            Documents
          </span>
          <strong>
            {
              health.documents
                .satisfied
            }/
            {
              health.documents
                .total
            }
          </strong>
          <small>
            {
              health.documents
                .missing
            } missing ·{' '}
            {
              health.documents
                .pending_review
            } pending review
          </small>
        </div>
      </div>

      <div className="cx-work-health-next">
        <span>
          Next action
        </span>
        <strong>
          {
            health.next_action
              .label
          }
        </strong>
      </div>

      {
        health.reasons.length > 0
          ? (
            <div className="cx-work-health-reasons">
              {
                health.reasons
                  .slice(0, 3)
                  .map(
                    (reason) => (
                      <span key={reason}>
                        {reason}
                      </span>
                    ),
                  )
              }
            </div>
          )
          : null
      }
    </section>
  );
}

`;

  insertAt(
    edits,
    statusTone.getFullStart(),
    indentBlock(
      healthComponent,
      newline
    ),
    "WorkHealthCard component"
  );

  // ==========================================================
  // WorkArea — AST scope
  // ==========================================================

  const workArea =
    namedFunction(
      sourceFile,
      "WorkArea"
    );

  if (!workArea.body) {
    throw new Error(
      "WorkArea body not found."
    );
  }

  // State goes after WorkArea's direct `editing`.
  const editing =
    directVariable(
      workArea,
      "editing"
    );

  const stateText = `

  const [
    workHealth,
    setWorkHealth,
  ] = useState<WorkHealthSnapshot | null>(
    null,
  );

  const [
    workHealthLoading,
    setWorkHealthLoading,
  ] = useState(false);

  const [
    workHealthError,
    setWorkHealthError,
  ] = useState('');
`;

  insertAt(
    edits,
    editing.statement.end,
    indentBlock(
      stateText,
      newline
    ),
    "WorkArea health state"
  );

  // Loader goes after WorkArea's direct pendingAction.
  const pendingAction =
    directVariable(
      workArea,
      "pendingAction"
    );

  const loaderText = `

  const loadWorkHealth = (): void => {
    const workItemId =
      String(
        editing?.id ?? '',
      );

    if (!workItemId) {
      setWorkHealth(null);
      setWorkHealthLoading(false);
      setWorkHealthError('');
      return;
    }

    setWorkHealthLoading(true);

    void getObject(
      \`work-items/\${workItemId}/health\`,
    )
      .then((snapshot) => {
        setWorkHealth(
          snapshot as unknown as
            WorkHealthSnapshot,
        );

        setWorkHealthError('');
      })
      .catch((error: unknown) => {
        setWorkHealth(null);

        setWorkHealthError(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        );
      })
      .finally(() => {
        setWorkHealthLoading(false);
      });
  };

  useEffect(() => {
    loadWorkHealth();
  }, [
    editing?.id,
    tab,
  ]);
`;

  insertAt(
    edits,
    pendingAction.statement.end,
    indentBlock(
      loaderText,
      newline
    ),
    "WorkArea health loader"
  );

  // Find closeWorkDrawer structurally inside WorkArea.
  const closeDrawer =
    directVariable(
      workArea,
      "closeWorkDrawer"
    );

  const closeInitializer =
    closeDrawer.declaration
      .initializer;

  if (
    !closeInitializer ||
    !ts.isArrowFunction(
      closeInitializer
    ) ||
    !ts.isBlock(
      closeInitializer.body
    )
  ) {
    throw new Error(
      "closeWorkDrawer is not a block arrow function."
    );
  }

  const resetText = `
    setWorkHealth(null);
    setWorkHealthError('');
`;

  insertAt(
    edits,
    closeInitializer.body
      .getStart(sourceFile) + 1,
    indentBlock(
      resetText,
      newline
    ),
    "WorkArea health reset"
  );

  // Find actual drawer JSX structurally.
  const drawer =
    findJsxByClass(
      workArea,
      "cx-drawer"
    );

  const heading =
    findJsxElement(
      drawer,
      "h3",
      "New Work Item"
    );

  const cardText = `

            {editing.id ? (
              <WorkHealthCard
                health={workHealth}
                loading={
                  workHealthLoading
                }
                error={
                  workHealthError
                }
              />
            ) : null}
`;

  insertAt(
    edits,
    heading.end,
    indentBlock(
      cardText,
      newline
    ),
    "WorkArea WorkHealthCard"
  );

  // ==========================================================
  // Apply + parse again before any write
  // ==========================================================

  const modified =
    applyEdits(
      original,
      edits
    );

  parse(
    filePath,
    modified
  );

  assertSingleText(
    modified,
    "export function WorkHealthCard",
    "WorkHealthCard"
  );

  assertSingleText(
    modified,
    "work-items/${workItemId}/health",
    "health endpoint"
  );

  assertSingleText(
    modified,
    "<WorkHealthCard",
    "health card render"
  );

  if (write) {
    writePreservingNewline(
      filePath,
      original,
      modified
    );
  }

  return {
    original,
    modified,
    edits,
  };
}


function main() {
  const mode =
    process.argv[2];

  const filePath =
    process.argv[3];

  if (
    !filePath ||
    !["--check", "--write"].includes(mode)
  ) {
    console.error(
      "Usage: node phase4a2-work-health.cjs " +
      "--check|--write <work.tsx>"
    );

    process.exit(2);
  }

  const result =
    patchWorkFile(
      filePath,
      mode === "--write"
    );

  console.log(
    `VRIDHI_CODEMOD_MODE=${mode}`
  );

  console.log(
    `VRIDHI_CODEMOD_EDITS=${result.edits.length}`
  );

  for (
    const edit of
    result.edits
  ) {
    console.log(
      `  ${edit.label}: ${edit.start}`
    );
  }

  console.log(
    "PHASE_4A2_STRUCTURAL_PATCH=PASS"
  );
}


main();
