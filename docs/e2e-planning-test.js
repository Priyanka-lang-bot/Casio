// Browser test for Phases 4-6: budgets, goals, money model, what-if, nudges,
// reports, coach and account settings. Needs the app running.
//   node docs/e2e-planning-test.js            (local: http://localhost:3000)
//   BASE_URL=https://your-site node docs/e2e-planning-test.js
require("fs").mkdirSync("./e2e-screenshots", { recursive: true });
const { chromium } = require("playwright");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const S = "./e2e-screenshots/p4-";
let pass = 0, fail = 0;
const check = (ok, msg) => { if (ok) { pass++; console.log("ok  ", msg); } else { fail++; console.log("FAIL", msg); } };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  const email = `plan${Date.now()}@example.com`;

  await page.goto(`${BASE}/register`);
  await page.getByLabel("Full name").fill("Demo Planner");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("secret123");
  await page.getByLabel("Confirm password").fill("secret123");
  await page.getByRole("button", { name: /create/i }).click();
  await page.waitForURL(/overview/);
  check(true, "registered");

  // Sample data from the empty dashboard
  await page.getByRole("button", { name: "Try with sample data" }).click();
  await page.waitForSelector("text=Last 6 months", { timeout: 60000 });
  await page.waitForTimeout(1500);
  check(await page.getByText("Let's get started").count() === 0, "sample data loaded, dashboard filled");
  await page.screenshot({ path: S + "01-overview.png", fullPage: true });

  // Budgets: add a suggested budget, then a tight one to trigger a nudge
  await page.goto(`${BASE}/budgets`);
  await page.waitForSelector("text=Suggested budgets");
  const addBtn = page.getByRole("button", { name: /^Add ₹/ }).first();
  await addBtn.click();
  await page.waitForSelector("text=Your budgets for");
  check(await page.locator("li:has-text('of ₹')").count() >= 1, "suggested budget added and tracked");
  await page.getByRole("button", { name: "Add budget" }).click();
  await page.getByLabel("Category").selectOption({ label: "Food and Dining" });
  await page.getByLabel(/Monthly limit/).fill("500");
  await page.getByRole("button", { name: "Save budget" }).click();
  await page.waitForSelector("text=Over budget");
  check(true, "tight Food budget shows Over budget");
  await page.reload();
  await page.waitForSelector("[aria-label='Nudges']", { timeout: 15000 });
  check(await page.getByText(/Food and Dining budget exceeded/).count() > 0, "budget nudge raised");
  await page.screenshot({ path: S + "02-budgets.png", fullPage: true });

  // Goals
  await page.goto(`${BASE}/goals`);
  await page.getByRole("button", { name: "Create it" }).click();
  await page.getByLabel("Monthly amount (optional)").fill("10000");
  await page.getByRole("button", { name: "Save goal" }).click();
  await page.waitForSelector("text=Emergency fund");
  await page.getByRole("button", { name: "New goal" }).click();
  await page.getByLabel("Goal name").fill("New laptop");
  await page.getByLabel("Type").selectOption("purchase");
  await page.getByLabel("Target amount").fill("80000");
  const d = new Date(); d.setMonth(d.getMonth() + 4);
  await page.getByLabel("Target date (optional)").fill(d.toISOString().slice(0, 10));
  await page.getByLabel("Monthly amount (optional)").fill("5000");
  await page.getByRole("button", { name: "Save goal" }).click();
  await page.waitForSelector("text=New laptop");
  check(await page.getByText("Behind").count() > 0, "laptop goal correctly marked Behind");
  await page.locator("div:has(> div > div > div:text('New laptop'))").first();
  await page.getByRole("button", { name: "Add money" }).nth(1).click();
  await page.getByLabel(/Amount/).fill("20000");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.waitForTimeout(800);
  check(await page.getByText("₹20,000").count() > 0, "contribution recorded");
  await page.screenshot({ path: S + "03-goals.png", fullPage: true });

  // What-if
  await page.goto(`${BASE}/what-if`);
  await page.getByRole("button", { name: "What if my rent increases by ₹3,000?" }).click();
  await page.waitForSelector("text=Savings over the next 12 months");
  check(await page.getByText(/less each month/).count() > 0, "rent what-if explains the impact");
  check(await page.getByText("Effect on your goals").count() > 0, "what-if shows goal effects");
  await page.screenshot({ path: S + "04-what-if.png", fullPage: true });
  await page.getByLabel("Value").fill("30");
  await page.getByRole("button", { name: "Run scenario" }).click();
  await page.waitForSelector("text=/more each month/");
  check(true, "step-by-step scenario (cut dining 30%) works");

  // Money model
  await page.goto(`${BASE}/money-model`);
  await page.waitForSelector("text=Savings forecast");
  check(await page.getByText("What really happened").count() > 0 && await page.getByText("What you told CASIO").count() > 0, "money model keeps actual and estimate apart");
  check(await page.getByText("Month by month").count() > 0, "snapshot history shown");
  await page.screenshot({ path: S + "05-money-model.png", fullPage: true });

  // Reports
  await page.goto(`${BASE}/reports`);
  await page.waitForSelector("text=in a nutshell", { timeout: 30000 });
  check(await page.getByText("Where the money went").count() > 0, "monthly report built");
  await page.screenshot({ path: S + "06-report.png", fullPage: true });

  // Coach
  await page.goto(`${BASE}/coach`);
  await page.getByRole("button", { name: "How are my budgets doing?" }).click();
  await page.waitForSelector("text=/Checked your/", { timeout: 60000 });
  check(await page.getByText(/Food and Dining/).count() > 0, "coach answers from real budget data");
  await page.getByLabel("Your question").fill("Which stocks should I buy?");
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForSelector("text=Safety rule applied", { timeout: 60000 });
  check(true, "coach refuses specific stock picks");
  await page.screenshot({ path: S + "07-coach.png", fullPage: true });

  // Every section loads with no sideways scroll on a phone
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: await ctx.storageState() });
  const mp = await phone.newPage();
  mp.on("pageerror", (e) => errors.push(e.message));
  for (const path of ["/overview", "/transactions", "/import", "/rules", "/budgets", "/subscriptions", "/profile", "/money-model", "/goals", "/what-if", "/reports", "/coach", "/settings"]) {
    await mp.goto(`${BASE}${path}`);
    await mp.waitForLoadState("networkidle");
    const notBuilt = await mp.getByText("Not built yet").count();
    const wide = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    check(!wide && notBuilt === 0, `phone: ${path} loads, no placeholder, no sideways scroll`);
  }
  await mp.goto(`${BASE}/what-if`);
  await mp.screenshot({ path: S + "08-mobile-what-if.png", fullPage: true });
  await phone.close();

  // Settings: export, password, delete
  await page.goto(`${BASE}/settings`);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByText("Download all my data").click()]);
  check(/casio-data-.*\.json/.test(download.suggestedFilename()), "data export downloads");
  await page.getByLabel("Current password").fill("secret123");
  await page.getByLabel("New password", { exact: true }).fill("newpass456");
  await page.getByLabel("Confirm new password").fill("newpass456");
  await page.getByRole("button", { name: "Change password" }).click();
  await page.waitForSelector("text=Password changed");
  check(true, "password changed");
  await page.getByRole("button", { name: "Delete my account" }).click();
  await page.getByLabel("Your password").fill("newpass456");
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await page.getByRole("button", { name: "Delete everything" }).click();
  await page.waitForURL(/login\?deleted=1/);
  check(await page.getByText("have been deleted").count() > 0, "account deleted, back at login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("newpass456");
  await page.getByRole("button", { name: /log in/i }).click();
  await page.waitForTimeout(1500);
  check(!page.url().includes("/overview"), "deleted account can't log in");

  // The deleted account's login attempt correctly gets a 401; ignore that one.
  const real = errors.filter((e) => !e.includes("401"));
  check(real.length === 0, `no browser errors ${real.length ? JSON.stringify(real.slice(0, 5)) : ""}`);
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
