const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');
const fs = require('fs');

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

function runHelper(command, documentText, filePath, output, extraArgs = []) {
  const helperPath = path.join(__dirname, 'python', 'vscode_helpers.py');
  const pythonExecutable = getPythonExecutable();
  const env = createToolEnv();
  const args = [helperPath, command];
  if (filePath) {
    args.push('--path', filePath);
  }
  if (extraArgs.length) {
    args.push(...extraArgs);
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

function wordPrefixAtPosition(document, position) {
  const text = document.lineAt(position.line).text.substring(0, position.character);
  const match = text.match(/([A-Za-z_\.][\w\.]*)$/);
  return match ? match[1] : '';
}

function registerCompletions(output) {
  const kindMap = {
    function: vscode.CompletionItemKind.Function,
    method: vscode.CompletionItemKind.Method,
    class: vscode.CompletionItemKind.Class,
    type: vscode.CompletionItemKind.Struct,
    keyword: vscode.CompletionItemKind.Keyword,
  };

  return vscode.languages.registerCompletionItemProvider('tinylanguage', {
    provideCompletionItems(document, position) {
      const prefix = wordPrefixAtPosition(document, position);
      const response = runHelper('completions', document.getText(), document.uri.fsPath, output, ['--prefix', prefix]);
      if (!response.stdout) {
        return [];
      }
      try {
        const parsed = JSON.parse(response.stdout);
        return parsed.map((item) => {
          const completion = new vscode.CompletionItem(item.label, kindMap[item.kind] || vscode.CompletionItemKind.Text);
          completion.insertText = item.label;
          return completion;
        });
      } catch (err) {
        output.appendLine(`[TinyLanguage] Failed to parse completions: ${err}`);
        return [];
      }
    },
  });
}

function registerHover(output) {
  return vscode.languages.registerHoverProvider('tinylanguage', {
    provideHover(document, position) {
      const range = document.getWordRangeAtPosition(position, /[A-Za-z_\.]+/);
      if (!range) {
        return null;
      }
      const symbol = document.getText(range);
      const response = runHelper('hover', document.getText(), document.uri.fsPath, output, ['--symbol', symbol]);
      if (!response.stdout) {
        return null;
      }
      try {
        const parsed = JSON.parse(response.stdout);
        if (!parsed) {
          return null;
        }
        const markdown = new vscode.MarkdownString();
        markdown.appendCodeblock(parsed.detail || parsed.symbol, 'tinylanguage');
        return new vscode.Hover(markdown, range);
      } catch (err) {
        output.appendLine(`[TinyLanguage] Failed to parse hover payload: ${err}`);
        return null;
      }
    },
  });
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

function registerDebugAdapterExecutable(output) {
  return vscode.commands.registerCommand('tinylanguage.getDebugAdapterExecutable', () => {
    const pythonExecutable = getPythonExecutable();
    const adapterPath = path.join(__dirname, 'python', 'tiny_debug_adapter.py');
    const env = createToolEnv();
    output.appendLine(`[TinyLanguage] Launching debug adapter via ${pythonExecutable} ${adapterPath}`);
    return new vscode.DebugAdapterExecutable(pythonExecutable, [adapterPath], { env });
  });
}

function registerDebugConfigurations(output) {
  const type = 'tinylanguage';
  function describePython(pythonExecutable) {
    try {
      const probe = cp.spawnSync(pythonExecutable, ['-c', 'import sys; print(sys.executable)'], {
        encoding: 'utf-8',
      });
      if (probe.error) {
        return `not found (${probe.error.message})`;
      }
      if (probe.status !== 0) {
        return `unavailable (exit ${probe.status}: ${probe.stderr.trim()})`;
      }
      return probe.stdout.trim();
    } catch (err) {
      return `not found (${err.message})`;
    }
  }
  const provider = {
    provideDebugConfigurations(folder) {
      const runtimePath = getRuntimePath() || '${workspaceFolder}/src/tiny_language.py';
      return [
        {
          name: 'TinyLanguage: Launch active file (prototype)',
          type,
          request: 'launch',
          program: '${file}',
          runtime: runtimePath,
          python: getPythonExecutable(),
          stopOnEntry: false,
        },
      ];
    },
    resolveDebugConfiguration(folder, config) {
      if (!config || config.type !== type) {
        return config;
      }
      if (!config.program) {
        vscode.window.showWarningMessage('No TinyLanguage file specified for debugging.');
        return null;
      }

      const pythonExecutable = config.python || getPythonExecutable();
      const runtimePath = config.runtime || getRuntimePath();
      const workspaceRoot = folder?.uri.fsPath || 'unknown workspace';
      output.appendLine(`[TinyLanguage] Resolving debug configuration for ${workspaceRoot}`);
      output.appendLine(`[TinyLanguage]  • Program: ${config.program}`);
      output.appendLine(`[TinyLanguage]  • Python executable: ${pythonExecutable}`);
      output.appendLine(`[TinyLanguage]  • Runtime: ${runtimePath || '<not set>'}`);
      if (!runtimePath) {
        output.appendLine('[TinyLanguage] Warning: runtime path is empty; set tinylanguage.runtimePath in settings if a custom interpreter is required.');
      }
      const merged = {
        ...config,
        type,
        python: pythonExecutable,
        runtime: runtimePath,
      };
      output.appendLine(`[TinyLanguage] Starting debugger for ${merged.program}`);
      return merged;
    },
    resolveDebugConfigurationWithSubstitutedVariables(folder, config) {
      if (!config || config.type !== type) {
        return config;
      }

      const workspaceRoot = folder?.uri.fsPath || 'unknown workspace';
      const pythonExecutable = config.python || getPythonExecutable();
      const runtimePath = config.runtime || getRuntimePath();
      const runtimeExists = runtimePath ? fs.existsSync(runtimePath) : false;

      if (!config.program) {
        vscode.window.showWarningMessage('No TinyLanguage file specified for debugging.');
        return null;
      }

      const fileExists = fs.existsSync(config.program);
      const unresolvedTokens = /\$\{[^}]+\}/.test(config.program);

      output.appendLine(`[TinyLanguage] Final debug configuration for ${workspaceRoot}`);
      output.appendLine(`[TinyLanguage]  • Program: ${config.program}${unresolvedTokens ? ' (contains unresolved variables)' : ''}${fileExists ? '' : ' (file not found)'}`);
      output.appendLine(`[TinyLanguage]  • Python executable: ${pythonExecutable} (${describePython(pythonExecutable)})`);
      output.appendLine(`[TinyLanguage]  • Runtime: ${runtimePath || '<not set>'}${runtimePath && !runtimeExists ? ' (file not found)' : ''}`);

      if (!fileExists) {
        vscode.window.showWarningMessage(`TinyLanguage debug target not found: ${config.program}`);
        return null;
      }

      if (runtimePath && !runtimeExists) {
        vscode.window.showWarningMessage(`TinyLanguage runtime not found: ${runtimePath}`);
        return null;
      }

      if (!runtimePath) {
        output.appendLine('[TinyLanguage] Warning: runtime path is empty; set tinylanguage.runtimePath in settings if a custom interpreter is required.');
      }

      const merged = {
        ...config,
        type,
        python: pythonExecutable,
        runtime: runtimePath,
      };

      output.appendLine(`[TinyLanguage] Launching debug adapter with resolved configuration.`);
      return merged;
    },
  };

  return vscode.debug.registerDebugConfigurationProvider(type, provider);
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
  const completions = registerCompletions(output);
  const hover = registerHover(output);
  const repl = registerRepl(output);
  const runFile = registerRunFile(output);
  const debugAdapterCommand = registerDebugAdapterExecutable(output);
  const debugConfigProvider = registerDebugConfigurations(output);
  const refreshCommand = registerRefreshDiagnostics(output, collection, refresh);

  context.subscriptions.push(
    output,
    collection,
    formatter,
    completions,
    hover,
    repl,
    runFile,
    debugAdapterCommand,
    debugConfigProvider,
    refreshCommand,
    ...disposables,
  );
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
