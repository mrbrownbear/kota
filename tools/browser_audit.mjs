import { chromium } from "playwright";
import fs from "node:fs";

const base = process.env.AUDIT_BASE || "http://127.0.0.1:8000";
const localOrigin = new URL(base).origin;
const routes = [
  "/",
  "/agency/",
  "/culture",
  "/contact",
  "/service/brand-strategy-and-identity/",
  "/service/web-design-development/",
  "/service/growth-marketing/",
  "/b2b-transformation/",
  "/healthcare/",
  "/media-entertainment/",
  "/retail/"
];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "no-preference",
  ignoreHTTPSErrors: true
});
const results = [];

for (const route of routes) {
  const page = await context.newPage();
  const external = [];
  const failed = [];
  const httpErrors = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on("request", req => {
    try {
      const u = new URL(req.url());
      if ((u.protocol === "http:" || u.protocol === "https:") && u.origin !== localOrigin) {
        external.push({ url: req.url(), type: req.resourceType() });
      }
    } catch {}
  });
  page.on("requestfailed", req => failed.push({
    url: req.url(),
    type: req.resourceType(),
    error: req.failure()?.errorText || "failed"
  }));
  page.on("response", res => {
    if (res.status() >= 400) httpErrors.push({ url: res.url(), status: res.status() });
  });
  page.on("console", msg => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", err => pageErrors.push(String(err.stack || err)));

  let navigationError = null;
  try {
    await page.goto(base + route, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(1400);

    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const steps = Math.min(12, Math.max(1, Math.ceil(height / 850)));
    for (let i = 0; i <= steps; i++) {
      await page.evaluate(([step, count, h]) => {
        window.scrollTo(0, Math.round(h * step / Math.max(1, count)));
      }, [i, steps, height]);
      await page.waitForTimeout(80);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
  } catch (e) {
    navigationError = String(e);
  }

  const state = await page.evaluate(() => {
    const images = [...document.images].map(x => ({
      src: x.currentSrc || x.src,
      complete: x.complete,
      width: x.naturalWidth,
      height: x.naturalHeight
    }));
    const videos = [...document.querySelectorAll("video")].map(x => ({
      src: x.currentSrc || x.src,
      readyState: x.readyState,
      networkState: x.networkState,
      error: x.error ? { code: x.error.code, message: x.error.message } : null
    }));
    const canvases = [...document.querySelectorAll("canvas")].map(x => ({
      width: x.width,
      height: x.height,
      rect: {
        width: x.getBoundingClientRect().width,
        height: x.getBoundingClientRect().height
      }
    }));
    const animations = document.getAnimations().map(a => ({
      playState: a.playState,
      currentTime: Number(a.currentTime || 0)
    }));
    const hero = [...document.querySelectorAll(
      '[class*="Hero_"], [class*="hero"], .rebelLetters, .againstLetters, .boringLetters'
    )].slice(0, 24).map(el => {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return {
        tag: el.tagName,
        cls: el.className?.baseVal || el.className || "",
        opacity: style.opacity,
        transform: style.transform,
        width: rect.width,
        height: rect.height
      };
    });

    return {
      title: document.title,
      bodyTextLength: document.body?.innerText?.length || 0,
      images,
      videos,
      canvases,
      animations,
      hero
    };
  }).catch(() => ({
    title: "",
    bodyTextLength: 0,
    images: [],
    videos: [],
    canvases: [],
    animations: [],
    hero: []
  }));

  const brokenImages = state.images.filter(x => x.complete && (!x.width || !x.height));
  const brokenVideos = state.videos.filter(x => x.error || (x.src && x.networkState === 3));

  results.push({
    route,
    navigationError,
    external: [...new Map(external.map(x => [x.url, x])).values()],
    failed: [...new Map(failed.map(x => [x.url, x])).values()],
    httpErrors: [...new Map(httpErrors.map(x => [x.url, x])).values()],
    consoleErrors: [...new Set(consoleErrors)],
    pageErrors: [...new Set(pageErrors)],
    brokenImages,
    brokenVideos,
    metrics: {
      title: state.title,
      bodyTextLength: state.bodyTextLength,
      imageCount: state.images.length,
      videoCount: state.videos.length,
      canvasCount: state.canvases.length,
      animationCount: state.animations.length,
      activeAnimationCount: state.animations.filter(x => x.playState === "running").length,
      canvases: state.canvases,
      hero: state.hero
    }
  });

  await page.close();
}

await browser.close();

const totals = {
  navigationErrors: results.filter(x => x.navigationError).length,
  externalRequests: results.reduce((n, x) => n + x.external.length, 0),
  failedRequests: results.reduce((n, x) => n + x.failed.length, 0),
  httpErrors: results.reduce((n, x) => n + x.httpErrors.length, 0),
  consoleErrors: results.reduce((n, x) => n + x.consoleErrors.length, 0),
  pageErrors: results.reduce((n, x) => n + x.pageErrors.length, 0),
  brokenImages: results.reduce((n, x) => n + x.brokenImages.length, 0),
  brokenVideos: results.reduce((n, x) => n + x.brokenVideos.length, 0)
};

const report = {
  generatedAt: new Date().toISOString(),
  base,
  routesChecked: results.length,
  totals,
  results
};

fs.writeFileSync("offline-browser-audit.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(totals, null, 2));

for (const r of results) {
  const hasIssue = r.navigationError || r.external.length || r.failed.length ||
    r.httpErrors.length || r.consoleErrors.length || r.pageErrors.length ||
    r.brokenImages.length || r.brokenVideos.length;

  console.log("\nROUTE", r.route, JSON.stringify(r.metrics));
  if (!hasIssue) continue;
  if (r.navigationError) console.log("NAV", r.navigationError);
  if (r.external.length) console.log("EXTERNAL", JSON.stringify(r.external.slice(0, 30), null, 2));
  if (r.failed.length) console.log("FAILED", JSON.stringify(r.failed.slice(0, 30), null, 2));
  if (r.httpErrors.length) console.log("HTTP", JSON.stringify(r.httpErrors.slice(0, 30), null, 2));
  if (r.consoleErrors.length) console.log("CONSOLE", JSON.stringify(r.consoleErrors.slice(0, 30), null, 2));
  if (r.pageErrors.length) console.log("PAGEERROR", JSON.stringify(r.pageErrors.slice(0, 30), null, 2));
  if (r.brokenImages.length) console.log("BROKEN_IMAGES", JSON.stringify(r.brokenImages.slice(0, 30), null, 2));
  if (r.brokenVideos.length) console.log("BROKEN_VIDEOS", JSON.stringify(r.brokenVideos.slice(0, 30), null, 2));
}

const fatal = totals.navigationErrors + totals.externalRequests + totals.failedRequests +
  totals.httpErrors + totals.pageErrors + totals.brokenImages + totals.brokenVideos;
if (fatal) process.exitCode = 1;
