"use strict";

const fs = require("fs");
const path = require("path");

const REPO = "D:\\CAFirm\\cafirm";

const ts = require(
  path.join(
    REPO,
    "frontend",
    "node_modules",
    "typescript"
  )
);


function detectNewline(text) {
  return text.includes("\r\n")
    ? "\r\n"
    : "\n";
}


function parse(filePath, text) {
  const kind =
    filePath.endsWith(".tsx")
      ? ts.ScriptKind.TSX
      : ts.ScriptKind.TS;

  const sourceFile = ts.createSourceFile(
    filePath,
    text,
    ts.ScriptTarget.Latest,
    true,
    kind
  );

  const diagnostics =
    sourceFile.parseDiagnostics || [];

  if (diagnostics.length) {
    const messages = diagnostics.map(
      (diagnostic) =>
        ts.flattenDiagnosticMessageText(
          diagnostic.messageText,
          "\n"
        )
    );

    throw new Error(
      "TypeScript parse failed:\n" +
      messages.join("\n")
    );
  }

  return sourceFile;
}


function walk(node, visitor) {
  visitor(node);

  node.forEachChild(
    (child) => walk(child, visitor)
  );
}


function namedFunction(sourceFile, name) {
  const matches = [];

  walk(sourceFile, (node) => {
    if (
      ts.isFunctionDeclaration(node) &&
      node.name &&
      node.name.text === name
    ) {
      matches.push(node);
    }
  });

  if (matches.length !== 1) {
    throw new Error(
      `Expected exactly one function ${name}; ` +
      `found ${matches.length}.`
    );
  }

  return matches[0];
}


function bindingContainsName(
  bindingName,
  name
) {
  if (ts.isIdentifier(bindingName)) {
    return bindingName.text === name;
  }

  if (
    ts.isArrayBindingPattern(bindingName) ||
    ts.isObjectBindingPattern(bindingName)
  ) {
    for (const element of bindingName.elements) {
      if (ts.isOmittedExpression(element)) {
        continue;
      }

      if (
        bindingContainsName(
          element.name,
          name
        )
      ) {
        return true;
      }
    }
  }

  return false;
}


function directVariable(functionNode, name) {
  if (!functionNode.body) {
    throw new Error(
      `Function ${functionNode.name?.text} has no body.`
    );
  }

  const matches = [];

  for (
    const statement of
    functionNode.body.statements
  ) {
    if (!ts.isVariableStatement(statement)) {
      continue;
    }

    for (
      const declaration of
      statement.declarationList.declarations
    ) {
      if (
        bindingContainsName(
          declaration.name,
          name
        )
      ) {
        matches.push({
          statement,
          declaration,
        });
      }
    }
  }

  if (matches.length !== 1) {
    throw new Error(
      `Expected exactly one direct binding ${name} ` +
      `inside ${functionNode.name?.text}; ` +
      `found ${matches.length}.`
    );
  }

  return matches[0];
}


function importDeclaration(
  sourceFile,
  moduleName
) {
  const matches =
    sourceFile.statements.filter(
      (statement) =>
        ts.isImportDeclaration(statement) &&
        ts.isStringLiteral(
          statement.moduleSpecifier
        ) &&
        statement.moduleSpecifier.text ===
          moduleName
    );

  if (matches.length !== 1) {
    throw new Error(
      `Expected one import from ${moduleName}; ` +
      `found ${matches.length}.`
    );
  }

  return matches[0];
}


function namedImportBindings(
  importNode
) {
  const bindings =
    importNode.importClause?.namedBindings;

  if (
    !bindings ||
    !ts.isNamedImports(bindings)
  ) {
    throw new Error(
      "Expected named imports."
    );
  }

  return bindings;
}


function jsxAttributeText(
  node,
  attributeName
) {
  if (
    !ts.isJsxElement(node) &&
    !ts.isJsxSelfClosingElement(node)
  ) {
    return null;
  }

  const attributes =
    ts.isJsxElement(node)
      ? node.openingElement.attributes.properties
      : node.attributes.properties;

  for (const attribute of attributes) {
    if (
      ts.isJsxAttribute(attribute) &&
      attribute.name.text === attributeName
    ) {
      if (
        attribute.initializer &&
        ts.isStringLiteral(
          attribute.initializer
        )
      ) {
        return attribute.initializer.text;
      }
    }
  }

  return null;
}


function findJsxByClass(
  root,
  className
) {
  const matches = [];

  walk(root, (node) => {
    if (
      (
        ts.isJsxElement(node) ||
        ts.isJsxSelfClosingElement(node)
      ) &&
      jsxAttributeText(
        node,
        "className"
      ) === className
    ) {
      matches.push(node);
    }
  });

  if (matches.length !== 1) {
    throw new Error(
      `Expected one JSX element with className=` +
      `${className}; found ${matches.length}.`
    );
  }

  return matches[0];
}


function findJsxElement(
  root,
  tagName,
  containsText
) {
  const matches = [];

  walk(root, (node) => {
    if (!ts.isJsxElement(node)) {
      return;
    }

    const tag =
      node.openingElement.tagName
        .getText();

    if (tag !== tagName) {
      return;
    }

    if (
      containsText &&
      !node.getText().includes(containsText)
    ) {
      return;
    }

    matches.push(node);
  });

  if (matches.length !== 1) {
    throw new Error(
      `Expected one <${tagName}> containing ` +
      `[${containsText}]; found ${matches.length}.`
    );
  }

  return matches[0];
}


function applyEdits(
  text,
  edits
) {
  const ordered = [...edits].sort(
    (a, b) => b.start - a.start
  );

  let previousStart = text.length + 1;

  for (const edit of ordered) {
    if (
      edit.start < 0 ||
      edit.end < edit.start ||
      edit.end > text.length
    ) {
      throw new Error(
        `Invalid edit ${edit.label}.`
      );
    }

    if (edit.end > previousStart) {
      throw new Error(
        `Overlapping edit detected: ` +
        `${edit.label}.`
      );
    }

    previousStart = edit.start;
  }

  let output = text;

  for (const edit of ordered) {
    output =
      output.slice(0, edit.start) +
      edit.text +
      output.slice(edit.end);
  }

  return output;
}


function insertAt(
  edits,
  position,
  text,
  label
) {
  edits.push({
    start: position,
    end: position,
    text,
    label,
  });
}


function replaceRange(
  edits,
  start,
  end,
  text,
  label
) {
  edits.push({
    start,
    end,
    text,
    label,
  });
}


function assertSingleText(
  text,
  value,
  label
) {
  const count =
    text.split(value).length - 1;

  if (count !== 1) {
    throw new Error(
      `${label}: expected exactly one occurrence, ` +
      `found ${count}.`
    );
  }
}


function writePreservingNewline(
  filePath,
  original,
  modified
) {
  const newline = detectNewline(original);

  let normalized =
    modified.replace(/\r\n/g, "\n");

  if (newline === "\r\n") {
    normalized =
      normalized.replace(/\n/g, "\r\n");
  }

  fs.writeFileSync(
    filePath,
    normalized,
    "utf8"
  );
}


module.exports = {
  REPO,
  ts,
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
  replaceRange,
  assertSingleText,
  detectNewline,
  writePreservingNewline,
};
