// Drive the live Sentinel dashboard and encode a demo GIF (pure JS, no ffmpeg).
import { chromium } from "playwright";
import { PNG } from "pngjs";
import gifenc from "gifenc";
import fs from "node:fs";

const { GIFEncoder, quantize, applyPalette } = gifenc;

const DASH = process.env.DASH_URL || "http://localhost:5173";
const API = process.env.API_URL || "http://localhost:8000";
const OUT = process.env.OUT || "../../docs/assets/demo.gif";
const W = 960, H = 600;

const frames = []; // { rgba, delay }

async function waitForUp(url, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (r.ok || r.status === 304) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`timed out waiting for ${url}`);
}

async function seedPrompts() {
  // Make the Prompt registry view non-empty for the demo.
  const post = (body) =>
    fetch(`${API}/api/prompts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => {});
  await post({
    name: "support-reply",
    template: "You are a concise, friendly support agent. Answer: {question}",
    variables: ["question"],
    description: "Initial support reply prompt.",
  });
  await post({
    name: "support-reply",
    template:
      "You are a support agent. Use only the provided context. Answer: {question}",
    variables: ["question"],
    description: "Add grounding instruction to reduce hallucinations.",
  });
  await post({
    name: "intent-classifier",
    template: "Classify the user's intent into one of: {labels}.\n\n{message}",
    variables: ["labels", "message"],
  });
}

async function snap(page, delay = 1500, settle = 700) {
  await page.waitForTimeout(settle);
  const buf = await page.screenshot({ type: "png" });
  const png = PNG.sync.read(buf);
  frames.push({ rgba: new Uint8Array(png.data), delay });
  process.stdout.write(`  frame ${frames.length} (${png.width}x${png.height})\n`);
}

async function main() {
  console.log("waiting for services...");
  await waitForUp(`${API}/health`);
  await waitForUp(DASH);
  await seedPrompts();

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();

  // Overview
  await page.goto(`${DASH}/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".cards .card", { timeout: 20000 });
  await page.waitForSelector("svg", { timeout: 20000 }); // recharts rendered
  await snap(page, 2200);

  // Traces list
  await page.getByRole("link", { name: "Traces" }).click();
  await page.waitForSelector("tbody tr", { timeout: 20000 });
  await snap(page, 1800);

  // Open the hallucination trace (low trust score + eval bars + alert)
  const flaky = page.locator("tbody tr", { hasText: "flaky-rag" }).first();
  if (await flaky.count()) {
    await flaky.click();
  } else {
    await page.locator("tbody tr").first().click();
  }
  await page.waitForSelector(".waterfall .wf-row", { timeout: 20000 });
  await snap(page, 2000);

  // Select the LLM span to reveal the trust evaluation bars
  const llmRow = page.locator(".wf-row", { hasText: "chat.completions" }).first();
  if (await llmRow.count()) {
    await llmRow.click();
    await page.waitForTimeout(400);
  }
  await snap(page, 2400);

  // Alerts
  await page.getByRole("link", { name: "Alerts" }).click();
  await page.waitForSelector("tbody tr, .empty", { timeout: 20000 });
  await snap(page, 2200);

  // Prompts registry
  await page.getByRole("link", { name: "Prompts" }).click();
  await page.waitForSelector("tbody tr, .empty", { timeout: 20000 });
  const firstPrompt = page.locator("tbody tr").first();
  if (await firstPrompt.count()) {
    await firstPrompt.click();
    await page.waitForTimeout(500);
  }
  await snap(page, 2400);

  // Back to Overview to close the loop
  await page.getByRole("link", { name: "Overview" }).click();
  await page.waitForSelector(".cards .card", { timeout: 20000 });
  await snap(page, 2000);

  await browser.close();

  // Encode GIF
  console.log(`encoding ${frames.length} frames -> ${OUT}`);
  const enc = GIFEncoder();
  for (const f of frames) {
    const palette = quantize(f.rgba, 256);
    const index = applyPalette(f.rgba, palette);
    enc.writeFrame(index, W, H, { palette, delay: f.delay });
  }
  enc.finish();
  fs.writeFileSync(OUT, Buffer.from(enc.bytes()));
  const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
  console.log(`wrote ${OUT} (${kb} KB)`);
}

main().catch((e) => {
  console.error("capture failed:", e);
  process.exit(1);
});
