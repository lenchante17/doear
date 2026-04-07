import { accessSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function canAccess(filePath) {
  try {
    accessSync(filePath);
    return true;
  } catch {
    return false;
  }
}

function chromiumExecutableCandidates() {
  switch (process.platform) {
    case 'darwin':
      return [
        path.join(
          'chrome-mac-arm64',
          'Google Chrome for Testing.app',
          'Contents',
          'MacOS',
          'Google Chrome for Testing',
        ),
        path.join(
          'chrome-mac',
          'Google Chrome for Testing.app',
          'Contents',
          'MacOS',
          'Google Chrome for Testing',
        ),
        path.join('chrome-mac-arm64', 'Chromium.app', 'Contents', 'MacOS', 'Chromium'),
        path.join('chrome-mac', 'Chromium.app', 'Contents', 'MacOS', 'Chromium'),
      ];
    case 'linux':
      return [path.join('chrome-linux', 'chrome'), path.join('chrome-linux64', 'chrome')];
    case 'win32':
      return [
        path.join('chrome-win', 'chrome.exe'),
        path.join('chrome-win64', 'chrome.exe'),
        path.join('chrome-win32', 'chrome.exe'),
      ];
    default:
      return [];
  }
}

function chromiumDirs(browserRoot) {
  try {
    return readdirSync(browserRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name.startsWith('chromium-'))
      .map((entry) => entry.name)
      .sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
  } catch {
    return [];
  }
}

function resolveBrowserPath() {
  const roots = [
    path.join(rootDir, 'node_modules', 'playwright-core', '.local-browsers'),
    path.join(rootDir, 'node_modules', 'playwright', '.local-browsers'),
  ];

  for (const browserRoot of roots) {
    for (const chromiumDir of chromiumDirs(browserRoot)) {
      for (const candidate of chromiumExecutableCandidates()) {
        const executablePath = path.join(browserRoot, chromiumDir, candidate);
        if (canAccess(executablePath)) return executablePath;
      }
    }
  }

  throw new Error(
    'Could not find a Playwright Chromium executable under node_modules. Run `npx playwright install chromium`.',
  );
}

const marpBin = path.join(
  rootDir,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'marp.cmd' : 'marp',
);

const browserPath = resolveBrowserPath();
const marpArgs = ['--browser', 'chrome', '--browser-path', browserPath, ...process.argv.slice(2)];
const result = spawnSync(marpBin, marpArgs, { cwd: rootDir, stdio: 'inherit' });

if (result.error) throw result.error;
process.exit(result.status ?? 1);
