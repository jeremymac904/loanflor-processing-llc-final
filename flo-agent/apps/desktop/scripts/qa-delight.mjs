import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { _electron } from '@playwright/test'

const desktopRoot = path.resolve(import.meta.dirname, '..')
const exe = path.join(desktopRoot, 'release', 'win-unpacked', 'Flo.exe')
const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'flo-delight-qa-'))
const dataDir = path.join(sandbox, 'user-data')
const hermesHome = path.join(sandbox, 'hermes-home')
const repoRoot = path.resolve(desktopRoot, '..', '..')
const realBackend = process.argv[3] === 'real'
const hermesPython = process.env.HERMES_DESKTOP_PYTHON ?? 'C:\\Users\\ashle\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe'
if (realBackend && !fs.existsSync(hermesPython)) throw new Error(`Missing Hermes Python: ${hermesPython}`)
fs.mkdirSync(dataDir, { recursive: true })
fs.mkdirSync(hermesHome, { recursive: true })
if (realBackend) fs.writeFileSync(path.join(hermesHome, 'config.yaml'), 'model:\n  default: llama3.2:3b\n  provider: ollama\n')
fs.writeFileSync(path.join(dataDir, 'window-state.json'), JSON.stringify({ width: 1220, height: 800, isMaximized: false }))
fs.writeFileSync(path.join(dataDir, 'zoom-state.json'), JSON.stringify({ zoomLevel: 0 }))
const safeEnv = Object.fromEntries(Object.entries(process.env).filter(([key, value]) =>
  value && !/(?:_API_KEY|_TOKEN|_SECRET|_PASSWORD|_CREDENTIALS|_ACCESS_KEY|_PRIVATE_KEY|_OAUTH_TOKEN)$/.test(key)
))
const app = await _electron.launch({
  executablePath: exe,
  args: ['--disable-gpu', '--no-sandbox'],
  env: {
    ...safeEnv,
    HERMES_HOME: hermesHome,
    HERMES_DESKTOP_USER_DATA_DIR: dataDir,
    HERMES_DESKTOP_IGNORE_EXISTING: '1',
    HERMES_DESKTOP_APP_NAME: `FloDelightQA-${Date.now()}`,
    HERMES_DESKTOP_SKIP_QUIT_CONFIRM: '1',
    ...(realBackend ? {
      HERMES_DESKTOP_HERMES_ROOT: repoRoot,
      HERMES_DESKTOP_PYTHON: hermesPython
    } : {
      HERMES_DESKTOP_BOOT_FAKE: '1',
      HERMES_DESKTOP_BOOT_FAKE_STEP_MS: '120'
    })
  }
})
try {
  const page = await app.firstWindow()
  await page.waitForSelector('#root', { timeout: 30_000 })
  await page.waitForTimeout(realBackend ? 12_000 : 5_000)
  if (realBackend) {
    const later = page.getByText("I'll choose a provider later", { exact: true })
    if (await later.isVisible().catch(() => false)) {
      await later.click()
      await page.waitForTimeout(4_000)
    }
    const continueButton = page.getByRole('button', { name: 'Continue', exact: true })
    if (await continueButton.isVisible().catch(() => false)) {
      await continueButton.click()
      await page.waitForTimeout(3_000)
    }
    const newSession = page.getByText('New session', { exact: true }).first()
    if (await newSession.isVisible().catch(() => false)) {
      await newSession.click()
      await page.waitForTimeout(2_000)
    }
  }
  const out = process.argv[2] ?? path.join(sandbox, 'packaged-flo.png')
  await page.screenshot({ path: out, fullPage: true })
  const summary = await page.evaluate(() => ({
    title: document.title,
    text: document.querySelector('#root')?.textContent?.slice(0, 1200),
    font: getComputedStyle(document.body).fontFamily,
    intro: Boolean(document.querySelector('[data-slot="aui_intro"]')),
    errors: document.querySelectorAll('[role="alert"]').length
  }))
  process.stdout.write(`${JSON.stringify({ screenshot: out, summary, sandbox }, null, 2)}\n`)
} finally {
  await app.close().catch(() => undefined)
}
