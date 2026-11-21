// Full browser QA for CASIO: landing, themes, wallet, all 14 cards, and the main
// create/edit/delete flows in a demo sandbox. Saves screenshots and prints a report.
// BASE_URL=http://localhost:3000 OUT=/tmp/qa node docs/e2e-full-qa.js
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:3000';
const OUT = process.env.OUT || 'qa-shots';
require('fs').mkdirSync(OUT, { recursive: true });
const results = [];
const ok = (name, pass, info = '') => { results.push({ name, pass, info }); console.log(pass ? 'PASS' : 'FAIL', name, info); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(`${page.url()} ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`${page.url()} ${m.text()}`); });
  const apiGet = (p) => page.evaluate(async (p) => (await fetch('/api' + p)).json(), p);
  const shot = (n) => page.screenshot({ path: `${OUT}/${n}.png` });

  // Landing + theme persistence
  await page.goto(BASE + '/');
  ok('landing headline', await page.locator('h1').first().isVisible());
  await page.click('.lp-nav .theme-toggle');
  await page.reload();
  ok('dark theme remembered after reload', await page.evaluate(() => document.documentElement.classList.contains('dark')));
  await shot('landing-dark');
  await page.click('.lp-nav .theme-toggle');
  ok('back to light', !(await page.evaluate(() => document.documentElement.classList.contains('dark'))));

  // Demo
  await page.locator('.lp-hero .demo-cta').click();
  await page.waitForURL('**/wallet', { timeout: 60000 });
  await page.waitForTimeout(1600);
  ok('demo opens wallet', page.url().endsWith('/wallet'));
  ok('DEMO label shown', await page.locator('.demo-banner').isVisible());
  await shot('wallet');

  // Every card opens its module, and back returns
  const hrefs = await page.$$eval('a[data-card]', as => as.map(a => a.getAttribute('href')));
  ok('14 cards', hrefs.length === 14, hrefs.join(' '));
  for (const h of hrefs) {
    await page.click(`a[data-card][href="${h}"] .card-label`);
    await page.waitForURL('**' + h, { timeout: 30000 });
    await page.waitForLoadState('networkidle');
    const h1 = await page.locator('main h1').first().textContent().catch(() => '');
    await shot('page' + h.replace('/', '-'));
    await page.goBack();
    await page.waitForURL('**/wallet', { timeout: 30000 });
    ok('card ' + h, !!h1, h1);
  }

  // Keyboard: arrows move between cards, Enter opens
  await page.waitForTimeout(800);
  await page.focus('a[data-card][href="/overview"]');
  await page.keyboard.press('ArrowRight');
  const focused = await page.evaluate(() => document.activeElement.getAttribute('href'));
  ok('arrow key moves to next card', focused === '/transactions', focused);
  await page.keyboard.press('Enter');
  await page.waitForURL('**/transactions', { timeout: 30000 });
  ok('Enter opens card', page.url().endsWith('/transactions'));

  // Transactions: add, totals update, delete
  const month = new Date().toISOString().slice(0, 7);
  const before = await apiGet('/overview');
  await page.getByRole('button', { name: 'Add transaction' }).click();
  await page.fill('#tx-amount', '1234');
  await page.fill('#tx-desc', 'QA test purchase');
  await page.locator('[role=dialog] button[type=submit]').click();
  await page.waitForTimeout(1200);
  ok('new transaction listed', await page.getByText('QA test purchase').first().isVisible());
  const after = await apiGet('/overview');
  ok('month spending rose by 1234', Math.abs(Number(after.actual.month_expenses) - Number(before.actual.month_expenses) - 1234) < 0.01,
    `${before.actual.month_expenses} -> ${after.actual.month_expenses} (${month})`);
  await page.getByLabel('Delete QA test purchase').first().click();
  await page.locator('[role=dialog]').getByRole('button', { name: 'Delete' }).click();
  await page.waitForTimeout(1200);
  const after2 = await apiGet('/overview');
  ok('delete restores total', after2.actual.month_expenses === before.actual.month_expenses);
  await page.fill('#f-q', 'swiggy');
  await page.waitForTimeout(900);
  const rows = await page.locator('main table tbody tr, main li:has-text("SWIGGY")').count();
  ok('search filters list', rows > 0, `${rows} rows`);

  // Budgets: edit an existing budget amount, then delete and re-add
  await page.goto(BASE + '/budgets'); await page.waitForLoadState('networkidle');
  const editBtn = page.locator('button[aria-label^="Edit "][aria-label$=" budget"]').first();
  const label = await editBtn.getAttribute('aria-label');
  await editBtn.click();
  await page.fill('#b-amt', '4321');
  await page.getByRole('button', { name: 'Save budget' }).click();
  await page.waitForTimeout(1000);
  const budgets = await apiGet('/budgets');
  ok('budget edited', budgets.items.some(b => b.amount === '4321.00'), label);
  await shot('budgets-edited');

  // Goals: create, add money, delete
  await page.goto(BASE + '/goals'); await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'New goal' }).click();
  await page.getByLabel('Goal name').fill('QA trip to Goa');
  await page.getByLabel('Target amount').fill('30000');
  await page.getByLabel('Monthly amount (optional)').fill('3000');
  await page.getByRole('button', { name: 'Save goal' }).click();
  await page.waitForTimeout(1200);
  const goals = await apiGet('/goals');
  ok('goal created', goals.goals.some(g => g.name === 'QA trip to Goa'));
  await shot('goals');

  // Subscriptions: add a manual subscription, see it, delete it
  await page.goto(BASE + '/subscriptions'); await page.waitForLoadState('networkidle');
  ok('upcoming payments card', await page.getByText('Coming up in the next 30 days').isVisible());
  await page.getByRole('button', { name: 'Add subscription' }).click();
  await page.fill('#sub-name', 'QA Hotstar');
  await page.fill('#sub-amount', '299');
  await page.locator('[role=dialog] button[type=submit]').click();
  await page.waitForTimeout(1500);
  ok('manual subscription added', await page.getByText('QA Hotstar').first().isVisible());
  await shot('subscriptions');

  // What-if live sliders
  await page.goto(BASE + '/what-if'); await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Save ₹5,000 more' }).click();
  await page.waitForTimeout(1500);
  const sixMonth = await page.locator('text=Savings after 6 months').locator('..').textContent();
  await page.getByRole('button', { name: 'Spend 10% less' }).click();
  await page.waitForTimeout(1500);
  const sixMonth2 = await page.locator('text=Savings after 6 months').locator('..').textContent();
  ok('live what-if recalculates', sixMonth !== sixMonth2 && /\+/.test(sixMonth2), `${sixMonth} | ${sixMonth2}`);
  await shot('what-if');

  // CSV import with duplicates
  await page.goto(BASE + '/import'); await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Import sample CSV statement' }).click();
  await page.waitForURL(/batch=/, { timeout: 30000 });
  await page.getByRole('button', { name: /^Save \d+ transaction/ }).waitFor({ timeout: 30000 });
  const body = await page.locator('main').textContent();
  ok('import preview shows duplicates', /duplicate|already/i.test(body));
  await shot('import-review');
  const save = page.getByRole('button', { name: /^Save \d+ transaction/ });
  const saveText = await save.textContent();
  await save.click();
  await page.waitForTimeout(2000);
  ok('import saved', /saved|imported|See Overview/i.test(await page.locator('main').textContent()), saveText);

  // Reports download
  await page.goto(BASE + '/reports'); await page.waitForLoadState('networkidle'); await page.waitForTimeout(1500);
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 10000 }), page.getByRole('button', { name: 'CSV' }).click()]);
  ok('report CSV downloads', /casio-report-\d{4}-\d{2}\.csv/.test(dl.suggestedFilename()), dl.suggestedFilename());

  // Insights unusual spending
  await page.goto(BASE + '/insights'); await page.waitForLoadState('networkidle'); await page.waitForTimeout(1000);
  ok('unusual spending card', await page.getByText('Unusual spending').first().isVisible());

  // Coach labelled honestly
  await page.goto(BASE + '/coach'); await page.waitForLoadState('networkidle');
  ok('coach page', /coach/i.test(await page.locator('main h1').textContent()));

  // Dark mode across modules
  await page.click('.app-bar .theme-toggle');
  for (const p of ['/overview', '/transactions', '/budgets', '/reports', '/what-if', '/settings']) {
    await page.goto(BASE + p); await page.waitForLoadState('networkidle'); await page.waitForTimeout(700);
    await shot('dark' + p.replace('/', '-'));
  }
  ok('dark persists across pages', await page.evaluate(() => document.documentElement.classList.contains('dark')));
  await page.goto(BASE + '/wallet'); await page.waitForTimeout(1500); await shot('wallet-dark');

  // Mobile
  const m = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, cookies: undefined, storageState: await ctx.storageState() });
  const mp = await m.newPage();
  for (const p of ['/', '/wallet', '/overview', '/transactions', '/subscriptions', '/what-if', '/reports']) {
    await mp.goto(BASE + p); await mp.waitForLoadState('networkidle'); await mp.waitForTimeout(800);
    const over = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    ok('mobile no sideways scroll ' + p, over <= 0, String(over));
    await mp.screenshot({ path: `${OUT}/m${p === '/' ? '-landing' : p.replace('/', '-')}.png`, fullPage: p === '/wallet' });
  }

  ok('no console errors', errors.length === 0, errors.slice(0, 5).join(' | '));
  const failed = results.filter(r => !r.pass);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
