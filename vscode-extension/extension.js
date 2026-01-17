const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const net = require('net');

let debugTerminal;

function isDebugTerminalEnabled() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  return Boolean(config.get('showDebugTerminal'));
}

function logDebug(output, message) {
  const formatted = `[TinyLanguage][debug] ${message}`;
  if (output?.appendLine) {
    output.appendLine(formatted);
  }
  // Mirror debug logs to the extension host console so they are visible in the
  // Extension Development Host debug output/terminal.
  console.log(formatted); // eslint-disable-line no-console
}

function getDebugTerminal(output) {
  if (!isDebugTerminalEnabled()) {
    logDebug(output, 'debugTerminal: skipped (disabled via configuration)');
    return undefined;
  }
  if (debugTerminal && !debugTerminal.exitStatus) {
    return debugTerminal;
  }
  debugTerminal = vscode.window.createTerminal({ name: 'TinyLanguage Debug Log' });
  logDebug(output, 'debugTerminal: created TinyLanguage Debug Log terminal');
  return debugTerminal;
}

function getPythonExecutable() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const python = config.get('pythonPath') || 'python';
  return python;
}

function resolveWorkspacePath(rawPath) {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceFolder) {
    return rawPath.replace('${workspaceFolder}', workspaceFolder);
  }
  return rawPath;
}

function getRuntimePath() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const rawPath = config.get('runtimePath') || '';
  return resolveWorkspacePath(rawPath);
}

function getCliPath() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const rawPath = config.get('cliPath') || '';
  if (rawPath) {
    return resolveWorkspacePath(rawPath);
  }
  const runtimePath = getRuntimePath();
  if (runtimePath) {
    if (runtimePath.endsWith('tiny_language_cli.py')) {
      return runtimePath;
    }
    if (runtimePath.endsWith('tiny_language.py') || runtimePath.endsWith('tiny_language_stitched.py')) {
      const candidate = runtimePath.replace(/tiny_language(?:_stitched)?\.py$/, 'tiny_language_cli.py');
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
  }
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceFolder) {
    const candidate = path.join(workspaceFolder, 'src', 'tiny_language_cli.py');
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return '';
}

function shouldDelegatePythonDebugging(config) {
  const setting = vscode.workspace.getConfiguration('tinylanguage');
  if (config.usePythonExtension !== undefined) {
    return Boolean(config.usePythonExtension);
  }
  const preferPython = setting.get('preferPythonExtensionDebugger');
  return preferPython !== undefined ? Boolean(preferPython) : true;
}

function getDebugLogPath() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const rawPath = config.get('debugLogPath') || '';
  if (rawPath) {
    return resolveWorkspacePath(rawPath);
  }
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceFolder) {
    return path.join(workspaceFolder, '.tinylanguage', 'debug-adapter.log');
  }
  return path.join(os.tmpdir(), 'tinylanguage', 'debug-adapter.log');
}

function getTraceLogPath() {
  const config = vscode.workspace.getConfiguration('tinylanguage');
  const rawPath = config.get('traceLogPath') || '';
  if (rawPath) {
    return resolveWorkspacePath(rawPath);
  }
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceFolder) {
    return path.join(workspaceFolder, '.tinylanguage', 'runtime-trace.log');
  }
  return '';
}

function findBundledRuntime() {
  const runtimeCandidates = [
    path.join(__dirname, '..', 'src', 'tiny_language.py'),
    path.join(__dirname, '..', 'src', 'tiny_language_stitched.py'),
    path.join(__dirname, 'src', 'tiny_language.py'),
    path.join(__dirname, 'src', 'tiny_language_stitched.py'),
  ];
  return runtimeCandidates.find((candidate) => fs.existsSync(candidate)) || '';
}

function findBundledCli() {
  const cliCandidates = [
    path.join(__dirname, '..', 'src', 'tiny_language_cli.py'),
    path.join(__dirname, 'src', 'tiny_language_cli.py'),
  ];
  return cliCandidates.find((candidate) => fs.existsSync(candidate)) || '';
}

function ensureDirectoryForFile(filePath, output, label) {
  if (!filePath) {
    return '';
  }
  const parentDir = path.dirname(filePath);
  try {
    fs.mkdirSync(parentDir, { recursive: true });
    return filePath;
  } catch (err) {
    output.appendLine(`[TinyLanguage] ${label} could not create ${parentDir}: ${err.message}`);
    return '';
  }
}

function normalizeEnvValue(value) {
  if (value === undefined || value === null) {
    return value;
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch (err) {
    return String(value);
  }
}

function createToolEnv(extraEnv = {}, output) {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const repoSrcCandidates = [path.join(__dirname, '..', 'src'), path.join(__dirname, 'src')];
  const repoSrc = repoSrcCandidates.find((candidate) => fs.existsSync(candidate));
  const searchPaths = [];
  if (workspaceFolder) {
    searchPaths.push(path.join(workspaceFolder, 'src'));
  }
  if (repoSrc) {
    searchPaths.push(repoSrc);
  }
  const combined = searchPaths.concat(process.env.PYTHONPATH ? [process.env.PYTHONPATH] : []).join(path.delimiter);
  const normalizedExtraEnv = Object.entries(extraEnv).reduce((acc, [key, value]) => {
    acc[key] = normalizeEnvValue(value);
    return acc;
  }, {});
  const env = { ...process.env, ...normalizedExtraEnv, PYTHONPATH: combined };
  logDebug(
    output,
    `createToolEnv: workspace=${workspaceFolder || '<none>'} searchPaths=${searchPaths.join(path.delimiter)} PYTHONPATH=${combined}`,
  );
  return env;
}

function runHelper(command, documentText, filePath, output, extraArgs = []) {
  const helperPath = path.join(__dirname, 'python', 'vscode_helpers.py');
  const pythonExecutable = getPythonExecutable();
  logDebug(output, `runHelper: command=${command} python=${pythonExecutable} file=${filePath || '<stdin>'}`);
  const env = createToolEnv({}, output);
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
  logDebug(output, `runHelper: completed with ${result.stdout?.length || 0} bytes stdout`);
  return { stdout: result.stdout };
}

function registerFormatter(output) {
  return vscode.languages.registerDocumentFormattingEditProvider('tinylanguage', {
    provideDocumentFormattingEdits(document) {
      logDebug(output, `formatter: formatting ${document.uri.fsPath}`);
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
    logDebug(output, `diagnostics: refreshing ${document.uri.fsPath}`);
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
      logDebug(output, `completions: prefix='${prefix}' at ${document.uri.fsPath}:${position.line + 1}:${position.character + 1}`);
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
      logDebug(output, `hover: symbol='${symbol}' at ${document.uri.fsPath}:${position.line + 1}:${position.character + 1}`);
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

function registerDefinitions(output) {
  return vscode.languages.registerDefinitionProvider('tinylanguage', {
    provideDefinition(document, position) {
      const range = document.getWordRangeAtPosition(position, /[A-Za-z_\.]+/);
      if (!range) {
        return null;
      }
      const symbol = document.getText(range);
      const cursor = `${position.line + 1}:${position.character + 1}`;
      logDebug(output, `definition: symbol='${symbol}' at ${document.uri.fsPath}:${cursor}`);
      const response = runHelper('definitions', document.getText(), document.uri.fsPath, output, [
        '--symbol',
        symbol,
        '--position',
        cursor,
      ]);
      if (!response.stdout) {
        return null;
      }
      try {
        const parsed = JSON.parse(response.stdout);
        if (!parsed) {
          return null;
        }
        const targetUri = document.uri;
        const targetPosition = new vscode.Position(Math.max(0, parsed.line - 1), Math.max(0, parsed.column - 1));
        return new vscode.Location(targetUri, targetPosition);
      } catch (err) {
        output.appendLine(`[TinyLanguage] Failed to parse definition payload: ${err}`);
        return null;
      }
    },
  });
}

function registerRepl(output) {
  return vscode.commands.registerCommand('tinylanguage.startRepl', () => {
    const pythonExecutable = getPythonExecutable();
    const runtimePath = getRuntimePath();
    logDebug(output, `repl: using python='${pythonExecutable}' runtime='${runtimePath}'`);
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
    logDebug(output, `runFile: using python='${pythonExecutable}' runtime='${runtimePath}' program='${document.uri.fsPath}'`);
    const terminal = vscode.window.createTerminal({ name: 'TinyLanguage Run' });
    terminal.show(true);
    terminal.sendText(`${pythonExecutable} ${runtimePath} ${document.uri.fsPath}`);
  });
}

function registerRunFileNative(output) {
  return vscode.commands.registerCommand('tinylanguage.runFileNative', () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'tinylanguage') {
      vscode.window.showInformationMessage('Open a TinyLanguage file to run it with the native backend.');
      return;
    }
    const document = editor.document;
    if (document.isDirty) {
      document.save();
    }
    const pythonExecutable = getPythonExecutable();
    let cliPath = getCliPath();
    if (!cliPath) {
      cliPath = findBundledCli();
    }
    if (!cliPath) {
      vscode.window.showWarningMessage('TinyLanguage CLI not found. Set tinylanguage.cliPath to tiny_language_cli.py.');
      return;
    }
    logDebug(
      output,
      `runFileNative: using python='${pythonExecutable}' cli='${cliPath}' program='${document.uri.fsPath}'`,
    );
    const terminal = vscode.window.createTerminal({ name: 'TinyLanguage Native Run' });
    terminal.show(true);
    terminal.sendText(`${pythonExecutable} ${cliPath} --backend native ${document.uri.fsPath}`);
  });
}

function registerDebugAdapterExecutable(output) {
  function probeDebugAdapter(pythonExecutable, adapterPath, env) {
    const probe = cp.spawnSync(pythonExecutable, [adapterPath, '--self-test'], {
      encoding: 'utf-8',
      env,
      timeout: 5000,
    });
    if (probe.error) {
      output.appendLine(`[TinyLanguage] Debug adapter self-test failed to start: ${probe.error.message}`);
      return false;
    }
    if (probe.timedOut) {
      output.appendLine('[TinyLanguage] Debug adapter self-test timed out after 5s; continuing without probe.');
      return true;
    }
    if (probe.status !== 0) {
      output.appendLine(
        `[TinyLanguage] Debug adapter self-test exited with ${probe.status}: ${probe.stderr || probe.stdout || '<no output>'}`,
      );
      return false;
    }
    const message = probe.stdout?.trim() || 'ok';
    output.appendLine(`[TinyLanguage] Debug adapter self-test succeeded: ${message}`);
    return true;
  }

  function findAvailablePort(host) {
    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.unref();
      server.on('error', reject);
      server.listen(0, host, () => {
        const address = server.address();
        if (!address || typeof address === 'string') {
          reject(new Error('Failed to allocate TCP port for debug adapter'));
          return;
        }
        server.close((closeErr) => {
          if (closeErr) {
            reject(closeErr);
          } else {
            resolve(address.port);
          }
        });
      });
    });
  }

  async function createAdapterExecutable(configuration = {}) {
    const pythonExecutable = configuration.python || getPythonExecutable();
    const adapterPath = path.join(__dirname, 'python', 'tiny_debug_adapter.py');
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    logDebug(output, `debugAdapter: preparing adapter using python='${pythonExecutable}' path='${adapterPath}'`);
    const runtimePath = configuration.runtime || getRuntimePath();
    const pythonMode = Boolean(configuration.pythonMode);
    if (pythonMode) {
      output.appendLine(
        '[TinyLanguage] pythonMode=true uses Python\'s built-in debugger (bdb/pdb); use the VS Code Python extension for full debugpy-backed debugging.',
      );
    }
    const normalizedConfigEnv = { ...(configuration.env || {}) };
    if (typeof normalizedConfigEnv.TINYLANGUAGE_DAP_LOG === 'string') {
      normalizedConfigEnv.TINYLANGUAGE_DAP_LOG = resolveWorkspacePath(normalizedConfigEnv.TINYLANGUAGE_DAP_LOG);
    }
    if (typeof normalizedConfigEnv.TINYLANG_TRACE_LOG === 'string') {
      normalizedConfigEnv.TINYLANG_TRACE_LOG = resolveWorkspacePath(normalizedConfigEnv.TINYLANG_TRACE_LOG);
    }
    const env = createToolEnv(normalizedConfigEnv, output);
    const logPath = ensureDirectoryForFile(
      normalizedConfigEnv.TINYLANGUAGE_DAP_LOG || getDebugLogPath(),
      output,
      'Debug adapter logging',
    );
    if (logPath && !env.TINYLANGUAGE_DAP_LOG) {
      env.TINYLANGUAGE_DAP_LOG = logPath;
      output.appendLine(`[TinyLanguage] Debug adapter logging enabled: ${logPath}`);
    } else if (env.TINYLANGUAGE_DAP_LOG) {
      output.appendLine(`[TinyLanguage] Debug adapter logging enabled via launch env: ${env.TINYLANGUAGE_DAP_LOG}`);
    }
    const traceLogPath = ensureDirectoryForFile(
      normalizedConfigEnv.TINYLANG_TRACE_LOG || getTraceLogPath(),
      output,
      'Runtime trace logging',
    );
    if (traceLogPath && !env.TINYLANG_TRACE_LOG) {
      env.TINYLANG_TRACE_LOG = traceLogPath;
      output.appendLine(`[TinyLanguage] Runtime trace logging enabled: ${traceLogPath}`);
    } else if (env.TINYLANG_TRACE_LOG) {
      output.appendLine(`[TinyLanguage] Runtime trace logging enabled via launch env: ${env.TINYLANG_TRACE_LOG}`);
    }
    const userWantsStderr = ['1', 1, true, 'true'].includes(env.TINYLANGUAGE_DAP_STDERR);
    const mirrorByDefault = Boolean(logPath) && normalizedConfigEnv.TINYLANGUAGE_DAP_STDERR === undefined;
    const logToStderr = userWantsStderr || mirrorByDefault;
    env.TINYLANGUAGE_DAP_STDERR = logToStderr ? '1' : undefined;
    if (logToStderr) {
      output.appendLine('[TinyLanguage] Debug adapter will mirror logs to stderr (TINYLANGUAGE_DAP_STDERR=1).');
    }
    const launchCwd = configuration.cwd || workspaceFolder;
    const terminal = getDebugTerminal(output);
    if (terminal) {
      terminal.show(true);
      terminal.sendText(
        `echo "[TinyLanguage] Debug adapter starting for ${configuration.program || '<unknown>'}"`,
      );
      terminal.sendText(
        `echo "[TinyLanguage] python=${pythonExecutable} runtime=${runtimePath || '<not set>'} cwd=${launchCwd || '<default>'}"`,
      );
      terminal.sendText(
        'echo "[TinyLanguage] Adapter uses tiny_debug_adapter.py (no debugpy launcher expected)"',
      );
      if (pythonMode) {
        terminal.sendText(
          'echo "[TinyLanguage] pythonMode uses stdlib bdb/pdb; use the VS Code Python debugger for full debugpy support"',
        );
      }
    }
    const ok = probeDebugAdapter(pythonExecutable, adapterPath, env);
    if (!ok) {
      const hint = env.TINYLANGUAGE_DAP_LOG
        ? ` See ${env.TINYLANGUAGE_DAP_LOG} for details.`
        : '';
      const message =
        `TinyLanguage debug adapter self-test failed.${hint} Continuing to launch anyway; check Output → TinyLanguage for details.`;
      output.appendLine(`[TinyLanguage] ${message}`);
      vscode.window.showWarningMessage(message);
    }
    if (launchCwd) {
      output.appendLine(`[TinyLanguage] Debug adapter working directory: ${launchCwd}`);
    }
    const host = '127.0.0.1';
    let port;
    try {
      port = await findAvailablePort(host);
    } catch (err) {
      const reason = err?.message || err;
      output.appendLine(`[TinyLanguage] Failed to reserve TCP port for debug adapter: ${reason}`);
      return new vscode.DebugAdapterExecutable(pythonExecutable, [adapterPath], {
        env: {
          ...env,
          TINYLANGUAGE_RUNTIME: runtimePath,
        },
        cwd: launchCwd,
      });
    }

    const adapterEnv = {
      ...env,
      // Provide the runtime path to the adapter explicitly so it can load the
      // TinyLanguage interpreter even when the extension is installed without
      // the repository source tree available alongside it.
      TINYLANGUAGE_RUNTIME: runtimePath,
      TINYLANGUAGE_DAP_TCP_PORT: String(port),
      TINYLANGUAGE_DAP_TCP_HOST: host,
    };

    output.appendLine(
      `[TinyLanguage] Launching debug adapter on ${host}:${port} via ${pythonExecutable} ${adapterPath}`,
    );
    const child = cp.spawn(pythonExecutable, [adapterPath], {
      env: adapterEnv,
      cwd: launchCwd,
      stdio: 'pipe',
    });

    child.on('exit', (code, signal) => {
      const reason = signal ? `signal ${signal}` : `exit ${code}`;
      output.appendLine(`[TinyLanguage] Debug adapter exited (${reason})`);
    });
    child.stdout?.on('data', (chunk) => {
      const text = chunk.toString().trim();
      if (text) {
        output.appendLine(`[TinyLanguage][adapter stdout] ${text}`);
      }
    });
    child.stderr?.on('data', (chunk) => {
      const text = chunk.toString().trim();
      if (text) {
        output.appendLine(`[TinyLanguage][adapter stderr] ${text}`);
      }
    });

    return new vscode.DebugAdapterServer(port, host);
  }

  const command = vscode.commands.registerCommand('tinylanguage.getDebugAdapterExecutable', () => {
    logDebug(output, 'debugAdapter: command invoked for adapter executable');
    return createAdapterExecutable();
  });
  const factory = vscode.debug.registerDebugAdapterDescriptorFactory('tinylanguage', {
    createDebugAdapterDescriptor(session) {
      logDebug(output, `debugAdapter: factory requested for session ${session?.name || '<unnamed>'}`);
      return createAdapterExecutable(session?.configuration);
    },
  });

  return [command, factory];
}

function registerDebugConfigurations(output) {
  const type = 'tinylanguage';
  const supportedExtensions = new Set(['.tiny', '.py']);
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
      logDebug(output, `debugConfig: provide initial configurations for ${folder?.uri.fsPath || '<no workspace>'}`);
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
        {
          name: 'TinyLanguage: Launch active Python file (debug adapter test)',
          type,
          request: 'launch',
          program: '${file}',
          runtime: runtimePath,
          python: getPythonExecutable(),
          stopOnEntry: false,
          pythonMode: true,
        },
      ];
    },
    resolveDebugConfiguration(folder, config) {
      if (!config || config.type !== type) {
        return config;
      }
      logDebug(output, `debugConfig: resolve requested for program=${config.program || '<none>'}`);
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
      const programHasTokens = typeof config.program === 'string' && /\$\{[^}]+\}/.test(config.program);
      const programLooksPython =
        typeof config.program === 'string' && config.program.toLowerCase().endsWith('.py') && !programHasTokens;
      const pythonModeExplicit = config.pythonMode;
      const pythonModeAuto = pythonModeExplicit === undefined && programLooksPython;
      const pythonModeEnabled = pythonModeExplicit === true || pythonModeAuto;
      if (config.pythonMode === undefined && programHasTokens) {
        output.appendLine('[TinyLanguage]  • Python mode: deferred until variables are substituted');
      } else if (pythonModeEnabled && config.pythonMode !== true) {
        output.appendLine(`[TinyLanguage]  • Python mode: enabled automatically for Python file ${config.program}`);
      } else {
        output.appendLine(`[TinyLanguage]  • Python mode: ${pythonModeEnabled ? 'enabled' : 'disabled'}`);
      }
      if (!runtimePath) {
        output.appendLine('[TinyLanguage] Warning: runtime path is empty; set tinylanguage.runtimePath in settings if a custom interpreter is required.');
      }
      const merged = {
        ...config,
        type,
        python: pythonExecutable,
        runtime: runtimePath,
        pythonMode:
          pythonModeExplicit !== undefined
            ? pythonModeEnabled
            : programHasTokens
              ? undefined
              : pythonModeEnabled,
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
      let runtimePath = config.runtime || getRuntimePath();
      let runtimeExists = runtimePath ? fs.existsSync(runtimePath) : false;
      logDebug(output, `debugConfig: resolveWithVariables start for ${workspaceRoot}`);
      if (!runtimeExists) {
        const bundledRuntime = findBundledRuntime();
        if (bundledRuntime) {
          output.appendLine(
            `[TinyLanguage] Runtime not found at ${runtimePath || '<empty>'}; using bundled runtime ${bundledRuntime}.`,
          );
          runtimePath = bundledRuntime;
          runtimeExists = true;
        }
      }

      if (!config.program) {
        vscode.window.showWarningMessage('No TinyLanguage file specified for debugging.');
        return null;
      }

      const fileExists = fs.existsSync(config.program);
      const unresolvedTokens = /\$\{[^}]+\}/.test(config.program);

      const ext = path.extname(config.program || '').toLowerCase();
      const supportedProgram = supportedExtensions.has(ext);
      if (fileExists && !supportedProgram) {
        const message =
          'TinyLanguage debugging only supports .tiny (TinyLanguage) or .py (Python) files. Open the file you want to debug and try again.';
        output.appendLine(`[TinyLanguage] ${message}`);
        vscode.window.showWarningMessage(message);
        return null;
      }

      output.appendLine(`[TinyLanguage] Final debug configuration for ${workspaceRoot}`);
      output.appendLine(`[TinyLanguage]  • Program: ${config.program}${unresolvedTokens ? ' (contains unresolved variables)' : ''}${fileExists ? '' : ' (file not found)'}`);
      output.appendLine(`[TinyLanguage]  • Python executable: ${pythonExecutable} (${describePython(pythonExecutable)})`);
      output.appendLine(`[TinyLanguage]  • Runtime: ${runtimePath || '<not set>'}${runtimePath && !runtimeExists ? ' (file not found)' : ''}`);
      const pythonModeEnabled =
        config.pythonMode === true ||
        (config.pythonMode === undefined && typeof config.program === 'string' && config.program.toLowerCase().endsWith('.py'));
      if (pythonModeEnabled && config.pythonMode !== true) {
        output.appendLine(`[TinyLanguage]  • Python mode: enabled automatically for Python file ${config.program}`);
      } else {
        output.appendLine(`[TinyLanguage]  • Python mode: ${pythonModeEnabled ? 'enabled' : 'disabled'}`);
      }

      if (pythonModeEnabled && shouldDelegatePythonDebugging(config)) {
        const pythonExtension = vscode.extensions.getExtension('ms-python.python');
        if (!pythonExtension) {
          output.appendLine('[TinyLanguage]  • Python extension not installed; using built-in adapter instead.');
        } else {
          const delegated = {
            name: config.name || 'TinyLanguage (Python via VS Code Python)',
            type: 'python',
            request: 'launch',
            program: config.program,
            python: pythonExecutable,
            console: config.console || 'integratedTerminal',
            cwd: config.cwd || folder?.uri.fsPath,
            env: config.env,
            args: config.args,
            justMyCode: config.justMyCode ?? false,
          };
          output.appendLine('[TinyLanguage] Redirecting Python debugging to the VS Code Python extension (debugpy).');
          output.appendLine('[TinyLanguage] Set "tinylanguage.preferPythonExtensionDebugger" or launch.json "usePythonExtension": false to use the built-in adapter.');
          return delegated;
        }
      }

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
        pythonMode: pythonModeEnabled,
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
      logDebug(output, `refreshDiagnostics: manual refresh for ${editor.document.uri.fsPath}`);
      refreshFn(editor.document);
      vscode.window.showInformationMessage('TinyLanguage diagnostics refreshed.');
    }
  });
}

function activate(context) {
  const output = vscode.window.createOutputChannel('TinyLanguage');
  logDebug(output, 'activate: creating output channel and registering providers');
  const collection = vscode.languages.createDiagnosticCollection('tinylanguage');
  const formatter = registerFormatter(output);
  const { refresh, disposables } = registerDiagnostics(output, collection);
  const completions = registerCompletions(output);
  const hover = registerHover(output);
  const definitions = registerDefinitions(output);
  const repl = registerRepl(output);
  const runFile = registerRunFile(output);
  const runFileNative = registerRunFileNative(output);
  const [debugAdapterCommand, debugAdapterFactory] = registerDebugAdapterExecutable(output);
  const debugConfigProvider = registerDebugConfigurations(output);
  const refreshCommand = registerRefreshDiagnostics(output, collection, refresh);

  context.subscriptions.push(
    output,
    collection,
    formatter,
    completions,
    hover,
    definitions,
    repl,
    runFile,
    runFileNative,
    debugAdapterCommand,
    debugAdapterFactory,
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
