// How the scan works: five panels, plain language, real numbers from the code.
const INK = "#1e1e1e";
const MUTED = "#495057";
const F = 5; // Excalifont

const AGENT = "#d0ebff";   // a model step
const CHECK = "#f1f3f5";   // a check the code runs
const HUMAN = "#b2f2bb";   // where a person decides
const SET = "#fff3bf";     // settings
const OUT = "#e5dbff";     // what you get
const WARN = "#ffe3e3";    // a rule that lowers a grade

const W = 1960;
const els = [];
let y = 0;

const text = (x, ty, t, size = 24, color = MUTED) =>
  els.push({ type: "text", x, y: ty, text: t, fontSize: size, fontFamily: F, strokeColor: color });

const box = (x, by, w, h, label, fill, o = {}) =>
  els.push({
    type: "rectangle", x, y: by, width: w, height: h,
    backgroundColor: fill, fillStyle: "solid", strokeColor: o.stroke || INK,
    strokeWidth: o.strokeWidth ?? 2, strokeStyle: o.strokeStyle ?? "solid",
    roughness: 1, roundness: { type: 3 },
    label: { text: label, fontSize: o.fontSize ?? 22, fontFamily: F, strokeColor: INK,
             verticalAlign: o.verticalAlign || "middle" },
  });

const arrow = (x, ay, points, o = {}) =>
  els.push({
    type: "arrow", x, y: ay, points,
    width: Math.max(...points.map((p) => Math.abs(p[0]))),
    height: Math.max(...points.map((p) => Math.abs(p[1]))),
    strokeColor: o.color ?? INK, strokeWidth: o.strokeWidth ?? 2,
    strokeStyle: o.strokeStyle ?? "solid", roughness: 1,
    endArrowhead: o.head === false ? null : "arrow", startArrowhead: null,
  });

const panel = (title, sub) => {
  text(0, y, title, 40, INK);
  if (sub) text(0, y + 52, sub, 24, MUTED);
  y += sub ? 110 : 70;
};

const rule = () => {
  els.push({ type: "line", x: 0, y: y, width: W, height: 0, points: [[0, 0], [W, 0]],
             strokeColor: "#adb5bd", strokeWidth: 1, strokeStyle: "dashed", roughness: 1 });
  y += 70;
};

// ============================ PANEL 1: the engine ============================
panel("1. How one scan runs",
      "The same machine runs both scans. Models search, read, and write; the code checks their work and decides what passes.");

box(0, y, W, 120, "THE PROFILE, SET BEFORE THE RUN\n"
  + "the question   ·   the criteria and what each is worth   ·   the themes   ·   the date windows   ·   the house rules",
  SET, { fontSize: 24 });
y += 175;

text(0, y, "Step one, for every organization on the list, one after another", 26);
y += 46;
const S1 = [
  ["SCOUT", "Finds the programs\nthis organization runs"],
  ["LIBRARIAN", "Finds the organization's\nown reports"],
  ["READER", "Reads the report and\ncopies the exact lines"],
  ["SCORER", "Marks it against\nthe criteria"],
  ["EVIDENCE", "Finds and reads\nstudies of this\nprogram (YES only)"],
  ["VERIFIER", "Tries to disprove\nthe claim"],
  ["AUDITOR", "Checks the whole\nchain fits together"],
];
const G = 26, w1 = (W - G * 6) / 7, h1 = 190;
S1.forEach(([n, s], i) => {
  const x = i * (w1 + G);
  box(x, y, w1, h1, `${n}\n\n${s}`, n === "EVIDENCE" ? "#e7f5ff" : AGENT, { fontSize: 21 });
  if (i < 6) arrow(x + w1 + 4, y + h1 / 2, [[0, 0], [G - 8, 0]]);
});
y += h1 + 34;

box(0, y, W, 150,
  "CHECKS THE CODE RUNS, WITH NO MODEL INVOLVED\n"
  + "a dead or out-of-date link is dropped before reading\n"
  + "every quote must be found word for word in the source\n"
  + "a news page can point to a program, but it never proves anything   ·   one report is read for one program only",
  CHECK, { strokeStyle: "dashed", strokeWidth: 1, fontSize: 22 });
y += 205;

box(0, y, W * 0.56, 84, "THE LONG LIST   ·   every program found, with its source, quotes, and dates", "#ffffff", { fontSize: 23 });
box(W * 0.6, y, W * 0.4, 84, "PEOPLE DECIDE   ·   keep, drop, add, or change a grade", HUMAN, { fontSize: 23, strokeWidth: 4 });
arrow(W * 0.56 + 6, y + 42, [[0, 0], [W * 0.04 - 12, 0]]);
y += 140;

text(0, y, "Step two, once a person has reviewed the list", 26);
y += 46;
const S2 = [
  ["THEMER", "Groups the programs\ninto themes"],
  ["THE GATES", "The code lowers any\ncall the evidence\ndoes not support"],
  ["WRITER", "Writes the report\nfrom the evidence"],
  ["EDITOR", "Rewrites it once to fix\nthe language checks"],
  ["WHAT YOU GET", "The report, the list,\nand the funder map"],
];
const w2 = (W - G * 4) / 5, h2 = 180;
S2.forEach(([n, s], i) => {
  const x = i * (w2 + G);
  const fill = n === "THE GATES" ? CHECK : n === "WHAT YOU GET" ? OUT : AGENT;
  box(x, y, w2, h2, `${n}\n\n${s}`, fill, { fontSize: 21, strokeStyle: n === "THE GATES" ? "dashed" : "solid" });
  if (i < 4) arrow(x + w2 + 4, y + h2 / 2, [[0, 0], [G - 8, 0]]);
});
y += h2 + 40;
text(0, y, "The rule behind all of it: a model may propose anything, and the code believes only what it can check itself.", 26, INK);
y += 70;
rule();

// ============================ PANEL 2: two scans ============================
panel("2. Two scans, one machine",
      "You pick the scan in the sidebar. Everything below changes with it, and the steps above stay the same.");

const colW = (W - 60) / 2;
const rows = [
  ["The question it asks",
   "Which new areas should the Hub enter?",
   "Which proven program designs should the Youth\nEmployment and Skills team adopt, and who funds them?"],
  ["What counts as a find",
   "An approach that is new, real, recent, and could\nbecome policy",
   "A named program design with evidence about\nwhether it actually works"],
  ["What it does with\nACET's current work",
   "Screens it out. Work ACET already runs is marked\nexisting, so it can never be recommended as new",
   "Starts from it. The ten themes are ACET's own six\nareas of work plus four it wants to explore"],
  ["What it calls its answers",
   "Enter, watch, or deepen",
   "Adopt, adapt, or watch"],
  ["How many it leads with",
   "The two cleanest new areas",
   "Up to five designs with the strongest evidence"],
  ["What you get at the end",
   "A theme scorecard, an evidence map, and a memo",
   "A short brief, a list of program design options,\nand a ranked funder map"],
];
box(0, y, 300, 60, "", "#ffffff", { strokeWidth: 0 });
box(320, y, colW - 160, 60, "HORIZON SCAN", AGENT, { fontSize: 24 });
box(320 + colW - 160 + 40, y, colW - 160, 60, "YES SCAN", "#e7f5ff", { fontSize: 24 });
y += 76;
rows.forEach(([k, a, b]) => {
  const lines = Math.max(a.split("\n").length, b.split("\n").length);
  const h = 44 + lines * 34;
  box(0, y, 300, h, k, CHECK, { fontSize: 21, strokeWidth: 0 });
  box(320, y, colW - 160, h, a, "#ffffff", { fontSize: 21 });
  box(320 + colW - 160 + 40, y, colW - 160, h, b, "#ffffff", { fontSize: 21 });
  y += h + 14;
});
y += 40;
rule();

// ============================ PANEL 3: horizon weights ============================
panel("3. How marks turn into a score, in the horizon scan",
      "Every theme is marked on four things. Two of them count double, because they matter most to the Hub.");

box(0, y, 560, 250,
  "WHAT A MARK IS WORTH\n\nstrong  =  3 points\npartial  =  2 points\nweak     =  1 point", CHECK, { fontSize: 24 });
const critX = 620;
box(critX, y, W - critX, 250,
  "WHAT EACH TEST IS WORTH\n\n"
  + "Mandate fit, does it move Africa's economy forward?          counts twice\n"
  + "Research to policy, could ACET turn it into real policy?      counts twice\n"
  + "African traction, is there real demand on the continent?     counts once\n"
  + "White space, is the ground open for ACET to lead?             counts once", "#ffffff", { fontSize: 23 });
y += 300;

box(0, y, W, 230,
  "A WORKED EXAMPLE\n\n"
  + "A theme marked strong on mandate fit, strong on research to policy, partial on African traction, and strong on white space:\n"
  + "(3 x 2)  +  (3 x 2)  +  (2 x 1)  +  (3 x 1)  =  17 points out of a possible 18\n"
  + "The two highest-scoring themes that are new or next door to ACET's work become the two areas to enter.\n"
  + "If only one theme is worth entering, the report says one. It never invents a second to fill the space.", SET, { fontSize: 23 });
y += 290;
box(0, y, W, 96,
  "THE RULE THE CODE ENFORCES   ·   if a theme matches work ACET already runs, it is marked existing and set to deepen, "
  + "whatever the model said about it", WARN, { fontSize: 23 });
y += 160;
rule();

// ============================ PANEL 4: the evidence ladder ============================
panel("4. How the evidence ladder works, in the YES scan",
      "This is the heart of the YES scan. It answers one question: how sure can we be that a program actually works?");

const LADDER = [
  ["E1", "Described only. Someone says the program exists, and nothing measures it.", "#f8f9fa"],
  ["E2", "A measured change, with nobody to compare against. Something moved, but we cannot say the program caused it.", "#f1f3f5"],
  ["E3", "A fair comparison. The program group is compared with a similar group that did not join.", "#e9ecef"],
  ["E4", "A randomized trial. People were put into the program by chance, which is the strongest test of one program.", "#d0ebff"],
  ["E5", "Repeated. A review of many studies, or trials in two or more different countries.", "#a5d8ff"],
];
LADDER.slice().reverse().forEach(([k, v, fill], i) => {
  const h = 92, indent = (4 - i) * 70;
  box(indent, y, W - indent, h, `${k}      ${v}`, fill, { fontSize: 23 });
  y += h + 12;
});
y += 40;

text(0, y, "Five rules the code applies, and the lowest one always wins", 28, INK);
y += 50;
const CAPS = [
  ["THE QUOTE MUST\nBE REAL", "The sentence naming\nthe method must be\nfound word for word\nin the document.\nIf not, the grade\nfalls to E2."],
  ["THE WORDS SET\nTHE LIMIT", "The grade can be\nno higher than the\nmethod named in\nthat sentence,\nwhatever the model\nclaimed."],
  ["SOMEONE ELSE MUST\nHAVE CHECKED IT", "E4 and E5 need an\noutside evaluator.\nResearchers working\nwith the program\ncount. Its own website\ndoes not, unless a\njournal published it."],
  ["RESULTS,\nNOT ACTIVITY", "Counting people\ntrained is not a result.\nA study that counts\nonly activity, or\nreports no result yet,\nfalls to E2."],
  ["IT MUST BE\nTHIS PROGRAM", "A study of a\ndifferent program\ncounts for nothing."],
];
const wc = (W - G * 4) / 5;
CAPS.forEach(([t, d], i) => {
  box(i * (wc + G), y, wc, 300, `${t}\n\n${d}`, WARN, { fontSize: 20 });
});
y += 350;

box(0, y, W * 0.48, 210,
  "WHAT EACH GRADE ALLOWS\n\n"
  + "Adopt: E4 or better, or E3 repeated in two African countries\n"
  + "Adapt: E3 or better\n"
  + "Watch: everything else\n\n"
  + "A model may suggest a call, and the code lowers it\nwhen the evidence does not reach.", "#ffffff", { fontSize: 22 });
box(W * 0.52, y, W * 0.48, 210,
  "AFRICA FIRST\n\n"
  + "A program running in Africa enters the list at E2 or better.\n"
  + "A program from elsewhere enters only at E3 or better, and must\n"
  + "say what would have to change to work in an African country.", SET, { fontSize: 22 });
y += 270;

text(0, y, "Three real examples from the trial run", 28, INK);
y += 50;
const EX = [
  ["A school subject in Rwanda\nand Uganda", "An outside team ran a randomized trial and reported\nresults.", "E4, adopt", "#d3f9d8"],
  ["A training program\nin Nigeria", "Its only study is a review of this kind of program across\n62 countries that never names it.", "Good evidence for\nthe design, not\nproof for this program", "#fff3bf"],
  ["An apprenticeship trial\nin Nigeria", "The trial is real but still running, and reports nothing yet.", "E2, watch", "#ffe3e3"],
];
const we = (W - G * 2) / 3;
EX.forEach(([t, d, v, fill], i) => {
  box(i * (we + G), y, we, 260, `${t}\n\n${d}\n\n${v}`, fill, { fontSize: 21 });
});
y += 320;
box(0, y, W, 130,
  "THE GRADE THEN BECOMES A MARK\n"
  + "E4 and E5 count as strong, E3 as partial, E1 and E2 as weak. That mark carries double weight in the score,\n"
  + "alongside the results the program moves and what ACET could do with it.", CHECK, { fontSize: 23 });
y += 185;
box(0, y, W, 150,
  "HOW OLD A SOURCE MAY BE\n"
  + "a program's own pages: 2023 to 2026, because the program must still be running\n"
  + "a study: 2015 to 2026, because good studies take years\n"
  + "a news page: recent, and never counted as proof", SET, { fontSize: 23 });
y += 205;
rule();

// ============================ PANEL 5: funders, language, models ============================
panel("5. Ranking funders, checking the writing, and which model does what");

box(0, y, W * 0.48, 330,
  "HOW A FUNDER'S SCORE IS BUILT, OUT OF 18\n\n"
  + "Themes it funds that match ours:  2 points each, up to 10\n"
  + "Priority countries it names:            1 point each, up to 3\n"
  + "                                                       or 1 for Africa-wide\n"
  + "ACET can apply:                              3 points, or 1 if unclear\n"
  + "Its plan still runs this year:            2 points\n\n"
  + "Every fact needs a sentence found on the funder's own page.\n"
  + "Anything that cannot be found there is written as not found,\n"
  + "and a call whose deadline has passed is dropped.", "#ffffff", { fontSize: 22 });

box(W * 0.52, y, W * 0.48, 330,
  "WHAT THE CODE CHECKS IN THE WRITTEN REPORT\n\n"
  + "A 14-year-old could read it, measured on reading level\n"
  + "Sentences neither choppy nor overlong, about 7 to 20 words\n"
  + "All ten themes named, so none is dropped or invented\n"
  + "No dashes, and no setting one idea against another\n"
  + "Numbers zero to nine written out, acronyms explained once\n"
  + "Nothing about how the work was done, only what was found\n\n"
  + "The editor gets one pass to fix these. Whatever is left goes\n"
  + "to the analyst as a note, because only a person can reword\n"
  + "something and keep its meaning.", CHECK, { fontSize: 22 });
y += 390;

text(0, y, "Which model runs which step, and why", 28, INK);
y += 50;
const ROUTE = [
  ["THE HARDEST THINKING", "Opus 5, high effort", "Finding the right study, grouping\nthemes, writing and editing the report", "#a5d8ff"],
  ["READING CAREFULLY", "Opus 5", "Reading reports and studies, and\nchecking claims. Every quote must\nmatch the source exactly.", "#d0ebff"],
  ["SEARCHING AND LISTING", "Sonnet 5", "Finding programs, reports, and\nfunder pages", "#e7f5ff"],
  ["SHORT, FIXED CHECKS", "Haiku 4.5", "Marking against a set list, and\nchecking a chain for consistency", "#f1f3f5"],
];
const wr = (W - G * 3) / 4;
ROUTE.forEach(([t, m, d, fill], i) => {
  box(i * (wr + G), y, wr, 250, `${t}\n\n${m}\n\n${d}`, fill, { fontSize: 21 });
});
y += 310;

box(0, y, W, 170,
  "WHO DECIDES WHAT\n\n"
  + "The models propose: they search, read, quote, and draft.\n"
  + "The code decides what is allowed: grades, dates, quotes, themes, and language are checked in plain rules anyone can read.\n"
  + "People decide what matters: the Hub keeps, drops, and adds programs, and can change a grade, with every change written down.",
  HUMAN, { fontSize: 23 });
y += 230;

export default els;
