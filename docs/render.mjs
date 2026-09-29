import puppeteer from "puppeteer-core";
import fs from "node:fs";

const scene = process.env.SCENE || "./scene.mjs";
const out = process.env.OUT || "system_at_a_glance";
const skeleton = (await import(scene + "?" + Date.now())).default;
const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const page = await browser.newPage();
page.on("console", (m) => console.log("page:", m.text()));
page.on("pageerror", (e) => console.log("pageerror:", e.message));
await page.goto("https://esm.sh/", { waitUntil: "domcontentloaded" });
await page.setContent(`<!doctype html><html><body style="margin:0;background:#fff"><div id="out"></div></body></html>`);

const result = await page.evaluate(async (skeleton) => {
  const ex = await import("https://esm.sh/@excalidraw/excalidraw@0.18.0?deps=react@19.0.0,react-dom@19.0.0");
  const elements = ex.convertToExcalidrawElements(skeleton, { regenerateIds: false });
  const appState = { exportBackground: true, viewBackgroundColor: "#ffffff", exportWithDarkMode: false, exportScale: 1 };
  const svg = await ex.exportToSvg({ elements, appState, files: {}, exportPadding: 40 });
  document.getElementById("out").appendChild(svg);
  const json = ex.serializeAsJSON(elements, { viewBackgroundColor: "#ffffff" }, {}, "local");
  const r = svg.getBoundingClientRect();
  return { json, w: r.width, h: r.height, svg: svg.outerHTML };
}, skeleton);

fs.writeFileSync(out + ".excalidraw", result.json);
fs.writeFileSync(out + ".svg", result.svg);
await page.setViewport({ width: Math.ceil(result.w), height: Math.ceil(result.h), deviceScaleFactor: 2 });
await new Promise((r) => setTimeout(r, 1500));
const el = await page.$("#out svg");
await el.screenshot({ path: out + ".png", omitBackground: false });
console.log("done", result.w, result.h);
await browser.close();
