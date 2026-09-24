import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const base = process.env.AUDIT_BASE || "http://127.0.0.1:8000";
const root = process.cwd();

function discoverRoutes() {
  const routes = new Set(["/"]);
  const skip = new Set([".git","_next","__external__","__sitecloner","images","matter","capture","tools","node_modules",".github"]);
  const walk = (dir, rel = "") => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      if (skip.has(ent.name)) continue;
      const abs = path.join(dir, ent.name);
      const r = path.posix.join(rel.replaceAll("\\","/"), ent.name);
      if (ent.isDirectory()) {
        const idx = path.join(abs, "index.html");
        if (fs.existsSync(idx)) routes.add("/" + r.replace(/\/index\.html$/,"") + "/");
        walk(abs, r);
      } else if (!path.extname(ent.name) && fs.statSync(abs).size > 1000) {
        const head = fs.readFileSync(abs, { encoding: "utf8", flag: "r" }).slice(0, 200);
        if (/<!doctype html|<html/i.test(head)) routes.add("/" + r);
      }
    }
  };
  walk(root);
  return [...routes].filter(r => !r.includes("__q_")).slice(0, 80);
}

const preferred = ["/","/agency/","/work/","/culture","/contact","/service/brand-strategy-and-identity/","/service/web-design-development/","/service/growth-marketing/","/b2b-transformation/","/healthcare/","/media-entertainment/","/retail/"];\nconst discovered = new Set(discoverRoutes());\nconst routes = preferred.filter(r => r === "/" || discovered.has(r) || discovered.has(r.replace(/\\/$/,"")) || discovered.has(r + "/"));
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "no-preference",
  ignoreHTTPSErrors: true,
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
    const u = new URL(req.url());
    if ((u.protocol === "http:" || u.protocol === "https:") && u.origin !== new URL(base).origin) {
      external.push({ url: req.url(), type: req.resourceType() });
    }
  });
  page.on("requestfailed", req => failed.push({
    url: req.url(), type: req.resourceType(), error: req.failure()?.errorText || "failed"
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
    await page.waitForTimeout(1800);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    for (let y = 0; y < height; y += Math.max(500, Math.floor(1000 * 0.75))) {
      await page.evaluate(v => window.scrollTo(0, v), y);
      await page.waitForTimeout(80);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(600);
  } catch (e) {
    navigationError = String(e);
  }

  const state = await page.evaluate(() => {
    const imgs = [...document.images].map(x => ({
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
      width: x.width, height: x.height,
      rect: { width: x.getBoundingClientRect().width, height: x.getBoundingClientRect().height }
    }));
    const animations = document.getAnimations().map(a => ({
      playState: a.playState,
      currentTime: Number(a.currentTime || 0)
    }));
    const hero = [...document.querySelectorAll('[class*="Hero_"], [class*="hero"], .rebelLetters, .againstLetters, .boringLetters')]
      .slice(0, 20).map(el => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return { tag: el.tagName, cls: el.className?.baseVal || el.className || "", opacity: s.opacity, transform: s.transform, width: r.width, height: r.height };
      });
    return {
      title: document.title,
      bodyTextLength: document.body?.innerText?.length || 0,
      images: imgs,
      videos,
      canvases,
      animations,
      hero
    };
  }).catch(() => ({images:[],videos:[],canvases:[],animations:[],hero:[]}));

  const brokenImages = state.images.filter(x => x.complete && (!x.width || !x.height));
  const brokenVideos = state.videos.filter(x => x.error || (x.src && x.networkState === 3));

  results.push({
    route, navigationError,
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

const report = {
  generatedAt: new Date().toISOString(),
  base,
  routesChecked: results.length,
  totals: {
    navigationErrors: results.filter(x => x.navigationError).length,
    externalRequests: results.reduce((n,x) => n + x.external.length, 0),
    failedRequests: results.reduce((n,x) => n + x.failed.length, 0),
    httpErrors: results.reduce((n,x) => n + x.httpErrors.length, 0),
    consoleErrors: results.reduce((n,x) => n + x.consoleErrors.length, 0),
    pageErrors: results.reduce((n,x) => n + x.pageErrors.length, 0),
    brokenImages: results.reduce((n,x) => n + x.brokenImages.length, 0),
    brokenVideos: results.reduce((n,x) => n + x.brokenVideos.length, 0)
  },
  results
};

fs.writeFileSync("offline-browser-audit.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report.totals, null, 2));

for (const r of results) {
  const has = r.navigationError || r.external.length || r.failed.length || r.httpErrors.length || r.pageErrors.length || r.brokenImages.length || r.brokenVideos.length;
  if (has) {
    console.log("\nROUTE", r.route);
    if (r.navigationError) console.log("NAV", r.navigationError);
    if (r.external.length) console.log("EXTERNAL", JSON.stringify(r.external.slice(0, 20), null, 2));
    if (r.failed.length) console.log("FAILED", JSON.stringify(r.failed.slice(0, 20), null, 2));
    if (r.httpErrors.length) console.log("HTTP", JSON.stringify(r.httpErrors.slice(0, 20), null, 2));
    if (r.pageErrors.length) console.log("PAGEERROR", JSON.stringify(r.pageErrors.slice(0, 20), null, 2));
    if (r.brokenImages.length) console.log("BROKEN_IMAGES", JSON.stringify(r.brokenImages.slice(0, 20), null, 2));
    if (r.brokenVideos.length) console.log("BROKEN_VIDEOS", JSON.stringify(r.brokenVideos.slice(0, 20), null, 2));
  }
}

const fatal = report.totals.navigationErrors + report.totals.externalRequests + report.totals.failedRequests +
  report.totals.httpErrors + report.totals.pageErrors + report.totals.brokenImages + report.totals.brokenVideos;
if (fatal) process.exitCode = 1;
