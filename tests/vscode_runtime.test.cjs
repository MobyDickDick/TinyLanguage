/* Exercise extension commands with the VS Code API boundary replaced by a recorder. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

const root = path.resolve(__dirname, '..');
const runtime = path.join(root, 'src', 'tiny_language.py');
const cli = path.join(root, 'src', 'tiny_language_cli.py');

function extension(settings = {}, probe = null, child = null) {
  const commands = new Map();
  const terminals = [];
  const probes = [];
  let provider;
  let factory;
  let saved = false;
  const vscode = {
    CompletionItemKind: { Function: 1, Variable: 2, Keyword: 3 },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: '/separate project' } }],
      getConfiguration: () => ({ get: (key) => settings[key] }),
      onDidOpenTextDocument: () => ({}),
      onDidChangeTextDocument: () => ({}),
      onDidCloseTextDocument: () => ({}),
      onDidSaveTextDocument: () => ({}),
      textDocuments: [],
    },
    window: {
      createOutputChannel: () => ({ appendLine() {} }),
      createTerminal: (options) => { terminals.push(options); return { show() {} }; },
      activeTextEditor: { document: {
        languageId: 'tinylanguage', isDirty: true, uri: { fsPath: '/Pröjekt with spaces/main.tiny' },
        save: async () => { saved = true; return true; },
      } },
      showWarningMessage() {},
      showInformationMessage() {},
    },
    commands: { registerCommand: (name, handler) => commands.set(name, handler) },
    debug: {
      registerDebugAdapterDescriptorFactory: (_type, value) => { factory = value; return {}; },
      registerDebugConfigurationProvider: (_type, value) => { provider = value; return {}; },
    },
    languages: new Proxy({}, { get: (_target, key) => key === 'createDiagnosticCollection'
      ? () => ({ delete() {}, set() {} }) : () => ({}) }),
    DebugAdapterServer: class { constructor(port, host) { this.port = port; this.host = host; } },
  };
  const cp = { spawnSync(python, args, options) {
    probes.push({ python, args, options });
    return probe ? probe(python, args, options) : {
      status: 0, stdout: JSON.stringify(args.at(-1) === 'tiny_language' ? runtime : cli),
    };
  }, spawn: () => child };
  const net = { createServer: () => ({ unref() {}, on() {},
    listen(_port, _host, callback) { setImmediate(callback); },
    address: () => ({ port: 12345 }), close: (callback) => callback() }) };
  const context = { module: { exports: {} }, __dirname: path.join(root, 'vscode-extension'),
    process, setTimeout, clearTimeout, console: { log() {} }, require: (name) => name === 'vscode' ? vscode
      : name === 'child_process' ? cp : name === 'net' ? net
        : name === 'fs' ? { ...fs, mkdirSync() {} } : require(name) };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'vscode-extension/extension.js'), 'utf8'), context);
  context.module.exports.activate({ subscriptions: [] });
  return { commands, terminals, probes, provider, factory, vscode, saved: () => saved };
}

test('installed discovery runs the configured Python and passes paths as separate arguments', async () => {
  const app = extension({ pythonPath: '/Python with spaces/python.exe' });
  await app.commands.get('tinylanguage.runFile')();
  const terminal = app.terminals[0];
  assert.equal(app.saved(), true);
  assert.equal(terminal.shellPath, '/Python with spaces/python.exe');
  assert.deepEqual(Array.from(terminal.shellArgs), [runtime, '/Pröjekt with spaces/main.tiny']);
  assert.ok(app.probes.every((p) => p.python === terminal.shellPath && p.options.timeout === 5000));
  assert.equal(terminal.env.TINYLANGUAGE_RUNTIME, runtime);
  assert.ok(!terminal.env.PYTHONPATH.includes('/separate project/src'));
});

test('native and REPL commands use the same discovered installation', async () => {
  const app = extension();
  await app.commands.get('tinylanguage.runFileNative')();
  app.commands.get('tinylanguage.startRepl')();
  assert.deepEqual(Array.from(app.terminals[0].shellArgs), [cli, '--backend', 'native', '/Pröjekt with spaces/main.tiny']);
  assert.deepEqual(Array.from(app.terminals[1].shellArgs), [runtime, '--repl']);
});

test('explicit workspace runtime overrides installed discovery for running and helpers', async () => {
  const app = extension({ runtimePath: '${workspaceFolder}/custom/runtime.py' });
  await app.commands.get('tinylanguage.runFile')();
  assert.equal(app.terminals[0].shellArgs[0], '/separate project/custom/runtime.py');
  assert.equal(app.terminals[0].env.TINYLANGUAGE_RUNTIME, '/separate project/custom/runtime.py');
  assert.equal(app.probes.length, 0);
});

test('per-launch Python selection governs debug runtime discovery', () => {
  const app = extension({ pythonPath: 'default-python' });
  const config = app.provider.resolveDebugConfiguration(null,
    { type: 'tinylanguage', program: '/separate/main.tiny', python: 'launch-python' });
  assert.equal(config.runtime, runtime);
  assert.ok(app.probes.every((p) => p.python === 'launch-python'));
});

test('failed save prevents execution', async () => {
  const app = extension();
  app.vscode.window.activeTextEditor.document.save = async () => false;
  await app.commands.get('tinylanguage.runFile')();
  await app.commands.get('tinylanguage.runFileNative')();
  assert.equal(app.terminals.length, 0);
});

test('failed or malformed discovery falls back to the development runtime', async () => {
  for (const result of [{ status: 1 }, { error: new Error('timeout') }, { status: 0, stdout: 'bad JSON' }]) {
    const app = extension({}, () => result);
    await app.commands.get('tinylanguage.runFile')();
    assert.equal(app.terminals[0].shellArgs[0], runtime);
  }
});

test('debug descriptor waits for a complete TCP readiness signal', async () => {
  const child = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdout = new EventEmitter();
  child.kill = () => {};
  const app = extension({ debugLogPath: '/nonexistent/log' }, null, child);
  let completed = false;
  const pending = app.factory.createDebugAdapterDescriptor({ configuration: {} }).then((value) => {
    completed = true;
    return value;
  });
  await new Promise(setImmediate);
  assert.equal(completed, false);
  child.stderr.emit('data', Buffer.from('TINYLANGUAGE_DAP_REA'));
  assert.equal(completed, false);
  child.stderr.emit('data', Buffer.from('DY\r\n'));
  const descriptor = await pending;
  assert.equal(descriptor.port, 12345);
  assert.equal(descriptor.host, '127.0.0.1');
});

test('debug startup failure rejects the descriptor and stops the child', async () => {
  const child = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdout = new EventEmitter();
  let killed = false;
  child.kill = () => { killed = true; };
  const app = extension({ debugLogPath: '/nonexistent/log' }, null, child);
  const pending = app.factory.createDebugAdapterDescriptor({ configuration: {} });
  await new Promise(setImmediate);
  child.emit('exit', 1);
  await assert.rejects(pending, /exited before listening/);
  assert.equal(killed, true);
});
