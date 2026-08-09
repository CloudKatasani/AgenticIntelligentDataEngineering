/**
 * End-to-end check: drive a real agent run through the UI exactly as a user
 * would, then confirm the artifacts are downloadable.
 */
import { chromium } from 'playwright'

const BASE = process.env.ADE_BASE_URL ?? 'http://127.0.0.1:8000'
const SHOTS = process.env.ADE_SHOT_DIR ?? '/tmp'

// Some environments ship a prebuilt browser; otherwise Playwright resolves its own.
const launchOptions = process.env.PLAYWRIGHT_CHROMIUM_PATH
  ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
  : {}
const browser = await chromium.launch(launchOptions)
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = []
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
page.on('pageerror', (e) => errors.push(String(e)))

// Agent 01 has no hard dependencies, so it runs from a clean install.
await page.goto(`${BASE}/agents/01`, { waitUntil: 'networkidle' })
await page.selectOption('select >> nth=2', 'RETAIL')
await page.waitForTimeout(600)

await page.locator('tbody input[type=checkbox]').first().check()
await page.locator('tbody input[type=checkbox]').nth(1).check()
await page.waitForTimeout(400)

await page.getByPlaceholder(/Onboarding the retail source/).fill(
  'Onboard the retail source for the customer-360 data product.',
)
await page.waitForTimeout(900)

await page.screenshot({ path: `${SHOTS}/e2e-configured.png` })

const runButton = page.getByRole('button', { name: /Run agent 01/ })
console.log('run enabled:', await runButton.isEnabled())
await runButton.click()
await page.waitForURL(/\/runs\/run_/, { timeout: 60_000 })
await page.waitForTimeout(1200)

const heading = (await page.locator('h1').first().textContent())?.trim()
const status = (await page.locator('.chip').filter({ hasText: /Succeeded|Awaiting/ }).first().textContent())?.trim()
const artifactCount = await page.locator('a[download]').count()
console.log(`run page -> ${heading} | status ${status} | ${artifactCount} download links`)

await page.screenshot({ path: `${SHOTS}/e2e-run.png`, fullPage: false })

// Open an artifact inline.
await page.getByRole('button', { name: 'View' }).first().click()
await page.waitForTimeout(600)
const preview = await page.locator('pre').first().textContent()
console.log('artifact preview length:', preview?.length ?? 0)

// Verify the bundle actually downloads.
const bundleHref = await page.locator('a[href*="/bundle"]').first().getAttribute('href')
const bundle = await page.request.get(`${BASE}${bundleHref}`)
console.log('bundle:', bundle.status(), bundle.headers()['content-type'], (await bundle.body()).length, 'bytes')

await page.screenshot({ path: `${SHOTS}/e2e-artifact.png`, fullPage: false })

console.log('CONSOLE ERRORS:', errors.length ? errors.slice(0, 5) : 'none')
await browser.close()
