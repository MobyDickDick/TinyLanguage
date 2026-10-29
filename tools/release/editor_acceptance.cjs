/* Run with VS Code --extensionTestsPath against an isolated installed project. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const vscode = require('vscode');

async function until(predicate, label) {
  const deadline = Date.now() + 30000;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, `Timed out: ${label}`);
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

exports.run = async function run() {
  const checks = [];
  const folder = vscode.workspace.workspaceFolders[0];
  const config = vscode.workspace.getConfiguration('tinylanguage', folder.uri);
  const python = process.env.TINY_EDITOR_PYTHON;
  assert.ok(python, 'TINY_EDITOR_PYTHON is required');
  await config.update('pythonPath', python, vscode.ConfigurationTarget.Workspace);
  await config.update('runtimePath', '', vscode.ConfigurationTarget.Workspace);
  await config.update('cliPath', '', vscode.ConfigurationTarget.Workspace);
  await config.update('debugLogPath', '', vscode.ConfigurationTarget.Workspace);
  await config.update('traceLogPath', '', vscode.ConfigurationTarget.Workspace);
  const extension = vscode.extensions.getExtension('tinylanguage.tinylanguage-vscode');
  assert.ok(extension);
  await extension.activate();
  checks.push('extension-activation');

  const file = vscode.Uri.file(path.join(folder.uri.fsPath, 'src', 'main.tiny'));
  const document = await vscode.workspace.openTextDocument(file);
  await vscode.window.showTextDocument(document);
  const edits = await vscode.commands.executeCommand('vscode.executeFormatDocumentProvider', file,
    { tabSize: 4, insertSpaces: true });
  assert.ok(edits.length);
  const change = new vscode.WorkspaceEdit();
  change.set(file, edits);
  assert.ok(await vscode.workspace.applyEdit(change));
  assert.ok(await document.save());
  checks.push('editor-formatting');

  const invalid = await vscode.workspace.openTextDocument({ language: 'tinylanguage', content: 'print(1+);' });
  await vscode.window.showTextDocument(invalid);
  await vscode.commands.executeCommand('tinylanguage.refreshDiagnostics');
  assert.ok(vscode.languages.getDiagnostics(invalid.uri).length);
  checks.push('editor-diagnostics');
  await vscode.window.showTextDocument(document);

  for (const [command, name, expected] of [
    ['tinylanguage.runFile', 'TinyLanguage Run', '16'],
    ['tinylanguage.runFileNative', 'TinyLanguage Native Run', '3'],
  ]) {
    if (command.endsWith('Native')) {
      const simple = await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(folder.uri.fsPath, 'backend.tiny')));
      await vscode.window.showTextDocument(simple);
    }
    await vscode.commands.executeCommand(command);
    const terminal = vscode.window.terminals.find((item) => item.name === name);
    assert.ok(terminal);
    const options = terminal.creationOptions;
    assert.equal(options.shellPath, python);
    assert.ok(Array.isArray(options.shellArgs));
    const result = cp.spawnSync(options.shellPath, options.shellArgs,
      { encoding: 'utf-8', env: { ...process.env, ...options.env }, cwd: folder.uri.fsPath });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), expected);
    terminal.dispose();
    checks.push(command);
  }

  const events = [];
  let stopped;
  let failure;
  const tracker = vscode.debug.registerDebugAdapterTrackerFactory('tinylanguage', {
    createDebugAdapterTracker(session) {
      return { onDidSendMessage(message) {
        events.push(message);
        if (message.event === 'stopped') {
          stopped = session;
        }
      }, onError(error) { failure = error; } };
    },
  });
  const breakpoint = new vscode.SourceBreakpoint(new vscode.Location(file, new vscode.Position(2, 0)));
  vscode.debug.addBreakpoints([breakpoint]);
  try {
    assert.ok(await vscode.debug.startDebugging(folder, {
      type: 'tinylanguage', name: 'Installed acceptance', request: 'launch',
      program: file.fsPath, python, stopOnEntry: false,
    }));
    await until(() => stopped || failure, 'debug breakpoint');
    if (failure) throw failure;
    const stack = await stopped.customRequest('stackTrace', { threadId: 1 });
    assert.equal(stack.stackFrames[0].line, 3);
    await stopped.customRequest('continue', { threadId: 1 });
    await until(() => events.some((event) => event.event === 'terminated'), 'debug termination');
    assert.ok(events.some((event) => event.event === 'output' && event.body.output.includes('16')));
    checks.push('editor-debug-breakpoint-stack-output-continue-terminate');
  } finally {
    tracker.dispose();
    vscode.debug.removeBreakpoints([breakpoint]);
    await vscode.debug.stopDebugging(stopped);
  }
  const report = { vscode: vscode.version, extension: extension.packageJSON.version,
    extensionPath: extension.extensionPath, python, checks };
  fs.writeFileSync(process.env.TINY_EDITOR_REPORT, JSON.stringify(report, null, 2) + '\n');
};
