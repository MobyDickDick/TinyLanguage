const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

function getPythonExecutable() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  return config.get('pythonPath') || 'python';
}

function getRuntimePath() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const rawPath = config.get('runtimePath') || '';
  if (workspaceFolder) {
    return rawPath.replace('${workspaceFolder}', workspaceFolder);
  }
  return rawPath;
}

function createToolEnv() {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const repoSrc = path.join(__dirname, '..', 'src');
  const searchPaths = [];
  if (workspaceFolder) {
    searchPaths.push(path.join(workspaceFolder, 'src'));
  }
  searchPaths.push(repoSrc);
  const combined = searchPaths.concat(process.env.PYTHONPATH ? [process.env.PYTHONPATH] : []).join(path.delimiter);
  return { ...process.env, PYTHONPATH: combined };
}

function runHelper(command, documentText, filePath, output) {
  const helperPath = path.join(__dirname, 'python', 'vscode_helpers.py');
  const pythonExecutable = getPythonExecutable();
  const env = createToolEnv();
  const args = [helperPath, command];
  if (filePath) {
    args.push('--path', filePath);
  }
  const result = cp.spawnSync(pythonExecutable, args, {
    input: documentText,
    encoding: 'utf-8',
    env,
  });
  if (result.error) {
    output.appendLine(`[TinyLanguage] Failed to run helper: ${result.error.message}`);
    return { error: result.error.message };
  }
  if (result.status !== 0) {
    output.appendLine(`[TinyLanguage] Helper exited with status ${result.status}: ${result.stderr}`);
    return { error: result.stderr || `Helper exited with ${result.status}` };
  }
  return { stdout: result.stdout };
}

function registerFormatter(output) {
  return vscode.languages.registerDocumentFormattingEditProvider('tinylanguage', {
    provideDocumentFormattingEdits(document) {
      const response = runHelper('format', document.getText(), document.uri.fsPath, output);
      if (!response.stdout) {
        return [];
      }
      const start = document.lineAt(0).range.start;
      const end = document.lineAt(document.lineCount - 1).range.end;
      return [vscode.TextEdit.replace(new vscode.Range(start, end), response.stdout)];
    },
  });
}

function registerDiagnostics(output, collection) {
  async function refresh(document) {
    if (document.languageId !== 'tinylanguage') {
      return;
    }
    const response = runHelper('diagnostics', document.getText(), document.uri.fsPath, output);
    if (!response.stdout) {
      collection.delete(document.uri);
      return;
    }
    try {
      const parsed = JSON.parse(response.stdout);
      const diagnostics = parsed.map((diag) => {
        const [startLine, startCol, endLine, endCol] = diag.range;
        const range = new vscode.Range(
          new vscode.Position(Math.max(0, startLine - 1), Math.max(0, startCol - 1)),
          new vscode.Position(Math.max(0, endLine - 1), Math.max(0, endCol - 1)),
        );
        const vscodeDiag = new vscode.Diagnostic(range, diag.message, vscode.DiagnosticSeverity.Warning);
        vscodeDiag.code = diag.code;
        vscodeDiag.source = 'TinyLanguage';
        return vscodeDiag;
      });
      collection.set(document.uri, diagnostics);
    } catch (err) {
      output.appendLine(`[TinyLanguage] Failed to parse diagnostics: ${err}`);
    }
  }

  const openListener = vscode.workspace.onDidOpenTextDocument(refresh);
  const changeListener = vscode.workspace.onDidChangeTextDocument((event) => refresh(event.document));
  const saveListener = vscode.workspace.onDidSaveTextDocument(refresh);
  vscode.workspace.textDocuments.forEach(refresh);

  return { refresh, disposables: [openListener, changeListener, saveListener] };
}

function registerRepl(output) {
  return vscode.commands.registerCommand('tinylanguage.startRepl', () => {
    const pythonExecutable = getPythonExecutable();
    const runtimePath = getRuntimePath();
    const terminal = vscode.window.createTerminal({ name: 'TinyLanguage REPL' });
    terminal.show(true);
    terminal.sendText(`${pythonExecutable} ${runtimePath} --repl`);
  });
}

function registerRunFile(output) {
  return vscode.commands.registerCommand('tinylanguage.runFile', () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'tinylanguage') {
      vscode.window.showInformationMessage('Open a TinyLanguage file to run it.');
      return;
    }
    const document = editor.document;
    if (document.isDirty) {
      document.save();
    }
    const pythonExecutable = getPythonExecutable();
    const runtimePath = getRuntimePath();
    const terminal = vscode.window.createTerminal({ name: 'TinyLanguage Run' });
    terminal.show(true);
    terminal.sendText(`${pythonExecutable} ${runtimePath} ${document.uri.fsPath}`);
  });
}

function registerRefreshDiagnostics(output, collection, refreshFn) {
  return vscode.commands.registerCommand('tinylanguage.refreshDiagnostics', () => {
    const editor = vscode.window.activeTextEditor;
    if (editor) {
      refreshFn(editor.document);
      vscode.window.showInformationMessage('TinyLanguage diagnostics refreshed.');
    }
  });
}

function activate(context) {
  const output = vscode.window.createOutputChannel('TinyLanguage');
  const collection = vscode.languages.createDiagnosticCollection('tinylanguage');
  const formatter = registerFormatter(output);
  const { refresh, disposables } = registerDiagnostics(output, collection);
  const repl = registerRepl(output);
  const runFile = registerRunFile(output);
  const refreshCommand = registerRefreshDiagnostics(output, collection, refresh);

  context.subscriptions.push(output, collection, formatter, repl, runFile, refreshCommand, ...disposables);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
