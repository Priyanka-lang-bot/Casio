// Browser test for the card wallet and the one-click demo.
// BASE_URL=https://casio-three.vercel.app OUT=/tmp/shots node docs/e2e-wallet-demo-test.js
// Starts a demo sandbox, opens all 14 cards (and goes back each time), checks keyboard
// navigation, the coach, a sample import and the mobile layout, and saves screenshots.
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:3000';
const OUT = process.env.OUT || 'shots';
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(BASE + '/login');
  await page.screenshot({ path: `${OUT}/01-login.png` });
  const t = Date.now();
  await page.getByRole('button', { name: /Try CASIO Demo/ }).click();
  await page.waitForURL('**/wallet', { timeout: 60000 });
  console.log('demo login ms', Date.now() - t);
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/02-wallet.png` });
  await page.hover('a[data-card][href="/budgets"] .card-label');
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/03-wallet-hover.png` });
  // every card opens the right page; back returns to the wallet
  const hrefs = await page.$$eval('a[data-card]', as => as.map(a => a.getAttribute('href')));
  console.log('cards', hrefs.length, hrefs.join(' '));
  for (const h of hrefs) {
    await page.click(`a[data-card][href="${h}"] .card-label`);
    await page.waitForURL('**' + h, { timeout: 30000 });
    await page.waitForLoadState('networkidle');
    const h1 = await page.locator('main h1').first().textContent().catch(() => '?');
    await page.goBack();
    await page.waitForURL('**/wallet', { timeout: 30000 });
    console.log('ok', h, '->', h1);
  }
  // keyboard
  await page.reload(); await page.waitForTimeout(1500);
  await page.focus('a[data-card][href="/overview"]');
  await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown');
  const focused = await page.evaluate(() => document.activeElement.getAttribute('href'));
  console.log('arrow focus ->', focused);
  await page.screenshot({ path: `${OUT}/04-wallet-keyboard.png` });
  await page.keyboard.press('Enter');
  await page.waitForURL('**' + focused);
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/05-inner-page.png` });
  await page.getByRole('button', { name: /All cards/ }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/06-switcher.png` });
  await page.keyboard.press('Escape');
  for (const p of ['overview', 'insights', 'subscriptions', 'what-if', 'goals', 'budgets', 'money-model', 'reports']) {
    await page.goto(BASE + '/' + p); await page.waitForLoadState('networkidle'); await page.waitForTimeout(700);
    await page.screenshot({ path: `${OUT}/p-${p}.png`, fullPage: true });
  }
  await page.goto(BASE + '/coach'); await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Why did my expenses increase this month?' }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/p-coach.png`, fullPage: true });
  await page.goto(BASE + '/import'); await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Import sample CSV statement' }).click();
  await page.waitForURL('**/import?batch=*', { timeout: 30000 }); await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/p-import-review.png`, fullPage: true });

  // mobile
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await m.addCookies(await ctx.cookies());
  const mp = await m.newPage();
  await mp.goto(BASE + '/wallet'); await mp.waitForTimeout(1800);
  await mp.screenshot({ path: `${OUT}/m-01-wallet.png` });
  await mp.screenshot({ path: `${OUT}/m-02-wallet-full.png`, fullPage: true });
  const sw = await mp.evaluate(() => document.documentElement.scrollWidth);
  console.log('mobile scrollWidth', sw);
  await mp.tap('a[data-card][href="/subscriptions"] .card-label');
  await mp.waitForURL('**/subscriptions'); await mp.waitForTimeout(900);
  await mp.screenshot({ path: `${OUT}/m-03-subs.png` });
  const sw2 = await mp.evaluate(() => document.documentElement.scrollWidth);
  console.log('mobile subs scrollWidth', sw2);
  console.log('errors', JSON.stringify(errors.slice(0, 10)));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
