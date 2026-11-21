// Browser test for Smart Import. Needs the app running on :3000 and :8000.
// Run from the repo root: node docs/e2e-import-test.js  (requires Playwright)
require("fs").mkdirSync("./e2e-screenshots", { recursive: true });
const { chromium } = require('playwright');
const S = './e2e-screenshots/';
const SAMPLES = require('path').join(__dirname, 'samples') + '/';
let pass = 0, fail = 0;
const check = (ok, msg) => { if (ok) { pass++; console.log('ok  ', msg); } else { fail++; console.log('FAIL', msg); } };
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  const email = `demo${Date.now()}@example.com`;
  await page.goto('http://localhost:3000/register');
  await page.getByLabel('Full name').fill('Demo User');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill('secret123');
  await page.getByLabel('Confirm password').fill('secret123');
  await page.getByRole('button', { name: /create/i }).click();
  await page.waitForURL(/overview/);
  check(true, 'registered');

  await page.goto('http://localhost:3000/import');
  await page.getByText('Drop your bank statement here').waitFor();
  await page.screenshot({ path: S + '01-import-start.png', fullPage: true });
  await page.getByLabel('Choose a statement file').setInputFiles(SAMPLES + 'sample-statement.csv');
  await page.waitForURL(/batch=/);
  await page.getByText('Check before saving').waitFor();
  check(await page.getByText('Ticked to save').isVisible(), 'review screen shows');
  check((await page.locator('li:has(input[aria-label="Description"])').count()) === 17, '17 rows listed');
  check(await page.getByText("Couldn't read the date").isVisible(), 'bad date flagged');
  const saveBtn = page.getByRole('button', { name: /^Save \d+ transactions?/ });
  check(await saveBtn.isDisabled(), 'save blocked while a row needs fixing');
  await page.screenshot({ path: S + '02-review.png', fullPage: true });

  // Fix the date
  const badRow = page.locator('li', { hasText: "Couldn't read the date" });
  const dateInput = badRow.getByLabel('Date');
  await dateInput.fill('2026-10-31');
  await dateInput.blur();
  await page.waitForTimeout(800);
  check(!(await page.getByText("Couldn't read the date").isVisible()), 'date fixed');
  check(await saveBtn.isEnabled(), 'save enabled after fix');

  // Change Swiggy category -> dialog -> change all
  const swiggy = page.locator('li', { has: page.locator('input[value*="SWIGGY"]') }).first();
  await swiggy.getByLabel('Category').selectOption({ label: 'Groceries' });
  // Phase 3: the "Remember this?" dialog replaced "Change similar rows too?"
  await page.getByText('Remember this for next time?').waitFor();
  await page.screenshot({ path: S + '03-similar-dialog.png' });
  await page.getByRole('radio', { name: /Only similar rows in this file \(1\)/ }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();
  await page.waitForTimeout(800);
  check((await page.getByText('You chose').count()) === 2, 'both Swiggy rows changed');

  // Filter: check category
  await page.getByRole('button', { name: /Check category/ }).click();
  const checkRows = await page.locator('li:has(input[aria-label="Description"])').count();
  check(checkRows >= 1, `check-category filter shows ${checkRows}`);
  await page.getByRole('button', { name: /^All/ }).click();

  // Untick Ramesh, save
  const ramesh = page.locator('li', { has: page.locator('input[value*="RAMESH"]') });
  await ramesh.getByRole('checkbox').click();
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Save 16 transactions' }).click();
  await page.getByText('Saved 16 transactions').waitFor();
  await page.screenshot({ path: S + '04-saved.png' });
  check(true, 'saved 16');

  await page.goto('http://localhost:3000/transactions');
  await page.getByText('Imported (CSV)').first().waitFor();
  check((await page.getByText('Imported (CSV)').count()) === 16, 'transactions show imported badge');

  // Re-upload same file -> duplicates unticked
  await page.goto('http://localhost:3000/import');
  await page.getByLabel('Choose a statement file').setInputFiles(SAMPLES + 'sample-statement.csv');
  await page.waitForURL(/batch=/);
  await page.getByText('already imported this exact file').waitFor();
  check((await page.getByText('Already in your transactions').count()) === 15, 're-upload: 15 exact duplicates flagged');
  await page.screenshot({ path: S + '05-duplicates.png', fullPage: true });
  await page.getByRole('button', { name: 'Cancel import' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel import' }).click();
  await page.waitForURL(u => !u.toString().includes('batch='));

  // SMS paste
  await page.getByRole('tab', { name: /Paste bank SMS/ }).click();
  await page.getByLabel('SMS messages').fill(require('fs').readFileSync(SAMPLES + 'sample-sms.txt', 'utf8'));
  await page.getByRole('button', { name: 'Read these messages' }).click();
  await page.waitForURL(/batch=/);
  await page.getByText('2 messages were skipped').waitFor();
  check((await page.locator('li:has(input[aria-label="Description"])').count()) === 5, 'SMS: 5 transactions');
  await page.screenshot({ path: S + '06-sms-review.png', fullPage: true });
  await page.goto('http://localhost:3000/import');

  // PDF
  await page.getByLabel('Choose a statement file').setInputFiles(SAMPLES + 'sample-statement.pdf');
  await page.waitForURL(/batch=/);
  await page.getByText('Check before saving').waitFor();
  check((await page.locator('li:has(input[aria-label="Description"])').count()) === 9, 'PDF: 9 transactions');
  await page.goto('http://localhost:3000/import');

  // Scanned PDF
  await page.getByLabel('Choose a statement file').setInputFiles(SAMPLES + 'sample-scanned.pdf');
  await page.getByText('looks like a scanned statement').waitFor();
  check(true, 'scanned PDF explained');
  // Wrong file type
  await page.getByLabel('Choose a statement file').setInputFiles({ name: 'x.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('PK\x03\x04') });
  await page.getByText('Excel files aren').waitFor();
  check(true, 'excel refused clearly');
  await page.screenshot({ path: S + '07-history.png', fullPage: true });

  // Overview reflects October import
  await page.goto('http://localhost:3000/overview');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: S + '08-overview.png', fullPage: true });

  // Mobile review
  const m = await browser.newContext({ ...require('playwright').devices['iPhone 13'] });
  await m.addCookies(await ctx.cookies());
  const mp = await m.newPage();
  await mp.goto('http://localhost:3000/import');
  await mp.getByRole('link', { name: 'Continue review' }).first().click();
  await mp.getByText('Check before saving').waitFor();
  const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(!overflow, 'mobile: no sideways scroll');
  await mp.screenshot({ path: S + '09-mobile-review.png' });
  await mp.locator('li:has(input[aria-label="Description"])').first().scrollIntoViewIfNeeded();
  await mp.evaluate(() => window.scrollBy(0, -80));
  await mp.screenshot({ path: S + '10-mobile-rows.png' });

  // Undo
  await page.goto('http://localhost:3000/import');
  await page.getByRole('button', { name: 'Undo import' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Undo import' }).click();
  await page.waitForTimeout(800);
  await page.goto('http://localhost:3000/transactions');
  await page.getByText('No transactions yet').waitFor();
  check(true, 'undo removed imported transactions');

  const real = errors.filter(e => !e.includes('422'));
  check(real.length === 0, 'no browser errors ' + JSON.stringify(real.slice(0, 3)));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
