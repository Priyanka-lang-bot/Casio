// Browser test for Phase 3: learned rules and subscriptions.
// Needs the app running on :3000 and :8000. Run from the repo root:
//   node docs/e2e-learning-test.js     (requires Playwright)
require("fs").mkdirSync("./e2e-screenshots", { recursive: true });
const { chromium } = require("playwright");
const S = "./e2e-screenshots/p3-";
const SAMPLE = require("path").join(__dirname, "samples", "sample-6-months.csv");
let pass = 0, fail = 0;
const check = (ok, msg) => { if (ok) { pass++; console.log("ok  ", msg); } else { fail++; console.log("FAIL", msg); } };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  await page.goto("http://localhost:3000/register");
  await page.getByLabel("Full name").fill("Demo User");
  await page.getByLabel("Email").fill(`learn${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("secret123");
  await page.getByLabel("Confirm password").fill("secret123");
  await page.getByRole("button", { name: /create/i }).click();
  await page.waitForURL(/overview/);
  check(true, "registered");

  // --- 1. Import 6 months, teach CASIO that Swiggy Instamart is groceries ---
  await page.goto("http://localhost:3000/import");
  await page.getByLabel("Choose a statement file").setInputFiles(SAMPLE);
  await page.getByText("Check before saving").waitFor();
  const insta = () => page.locator("li", { has: page.locator('input[value*="SWIGGY INSTAMART"]') });
  const nInsta = await insta().count();
  check(nInsta >= 3, `found ${nInsta} Swiggy Instamart rows`);
  check((await insta().first().getByLabel("Category").inputValue()) !== "", "rows have a category");
  await insta().first().getByLabel("Category").selectOption({ label: "Groceries" });
  const dlg = page.getByRole("dialog");
  await dlg.getByText("Remember this for next time?").waitFor();
  await dlg.getByText("CASIO suggests").waitFor();
  check(!(await dlg.getByText(/same change 2 times/).isVisible()), "first correction isn't counted twice");
  check(await dlg.getByText(/Only similar rows in this file/).isVisible(), "offers 'similar rows in this file'");
  await dlg.getByRole("radio", { name: /Always use Groceries/ }).click();
  await page.screenshot({ path: S + "01-learn-dialog.png" });
  await dlg.getByRole("button", { name: "Make the rule" }).click();
  await page.getByText(/Rule made: “swiggy instamart” → Groceries/).waitFor();
  await page.waitForTimeout(500);
  const ruleBadges = await insta().locator('[data-slot="badge"]', { hasText: "Your rule" }).count();
  check(ruleBadges === nInsta - 1, `other ${nInsta - 1} Instamart rows now say “Your rule” (${ruleBadges})`);
  const plainSwiggy = page.locator("li", { has: page.locator('input[value^="UPI-SWIGGY-"]') }).first();
  check((await plainSwiggy.getByLabel("Category").locator("option:checked").textContent()) === "Food and Dining", "plain Swiggy orders untouched");
  await page.screenshot({ path: S + "02-review-with-rule.png", fullPage: false });
  await page.getByRole("button", { name: /^Save \d+ transactions?/ }).click();
  await page.getByText(/^Saved \d+ transactions/).waitFor();
  check(true, "import saved");

  // --- 2. Subscriptions ---
  await page.goto("http://localhost:3000/subscriptions");
  await page.getByRole("heading", { name: "Subscriptions", exact: true }).first().waitFor();
  await page.getByText("Things to check").waitFor();
  check(await page.getByText(/Netflix went up from ₹649 to ₹799/).first().isVisible(), "Netflix price-rise alert");
  check(await page.getByText(/New regular payment: Openai Chatgpt/).isVisible(), "new subscription alert");
  check(await page.getByText(/No Spotify payment seen/).isVisible(), "missed Spotify alert");
  check(await page.getByText(/Bescom Electricity was ₹2,980/).isVisible(), "unusual electricity bill alert");
  check(await page.getByText("Payment not seen").isVisible(), "Spotify card shows payment not seen");
  check(!(await page.getByText(/^Swiggy$/).isVisible()), "food orders are not listed as subscriptions");
  check(await page.getByText("Every week").first().isVisible(), "weekly milk found");
  await page.screenshot({ path: S + "03-subscriptions.png", fullPage: true });
  const netflix = page.locator('[data-slot="card"]', { has: page.getByRole("button", { name: "Netflix", exact: true }) });
  await netflix.getByRole("button", { name: "Not using" }).click();
  await page.getByText("on services you said you don't use").waitFor();
  check(await page.getByText("₹9,588").first().isVisible(), "could save ₹9,588 a year");
  await netflix.getByText("Why CASIO thinks this repeats").click();
  check(await page.getByText(/Paid 6 times every month/).isVisible(), "explains why it repeats");

  // --- 3. Rules page ---
  await page.goto("http://localhost:3000/rules");
  await page.getByText("swiggy instamart", { exact: true }).waitFor();
  check(await page.getByText(/Used on \d+ transactions?/).isVisible(), "rule shows how often it was used");
  check(await page.getByText("Made a rule").isVisible(), "correction history shows the rule");
  await page.screenshot({ path: S + "04-rules.png", fullPage: true });

  // --- 4. Transactions: one-off, then repeated correction -> suggestion -> undo ---
  await page.goto("http://localhost:3000/transactions?q=UBER");
  await page.getByText("UPI-UBER INDIA").first().waitFor();
  const uber = page.locator("li", { hasText: "UPI-UBER INDIA" });
  await uber.nth(0).getByLabel(/Category for/).selectOption({ label: "Travel" });
  await dlg.getByText("Remember this for next time?").waitFor();
  await dlg.getByRole("radio", { name: /Just this transaction/ }).click();
  await dlg.getByRole("button", { name: "Done" }).click();
  await page.waitForTimeout(400);
  await uber.nth(1).getByLabel(/Category for/).selectOption({ label: "Travel" });
  await dlg.getByText(/made this same change 2 times/).waitFor();
  check(true, "second identical correction -> CASIO suggests a rule");
  await page.screenshot({ path: S + "05-suggests-rule.png" });
  await dlg.getByRole("button", { name: "Make the rule" }).click();
  await page.getByText(/Rule made: shop “uber.*” → Travel/).waitFor();
  check(await page.getByText("Your rule").first().isVisible(), "transactions show “Your rule”");
  await page.screenshot({ path: S + "06-rule-made.png" });
  await page.getByRole("button", { name: "Undo" }).click();
  await page.getByText(/Rule removed\. \d+ transactions? went back/).waitFor();
  check(true, "undo removes the rule and restores categories");

  // --- 5. Overview shows the nudges ---
  await page.goto("http://localhost:3000/overview");
  await page.getByText("Your regular payments changed").waitFor();
  check(true, "overview shows subscription alerts");

  // --- 6. Phone ---
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://localhost:3000/subscriptions");
  await page.getByText("Things to check").waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(!overflow, "no sideways scrolling on a phone");
  await page.screenshot({ path: S + "07-mobile-subscriptions.png", fullPage: true });

  check(errors.length === 0, `no browser errors ${errors.length ? JSON.stringify(errors.slice(0, 3)) : ""}`);
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
