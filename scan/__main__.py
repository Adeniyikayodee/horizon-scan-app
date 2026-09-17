"""CLI.

  python -m scan init                      scaffold a sample org sheet
  python -m scan run --stage 1 [--only F]  scan + score  -> review/
  python -m scan run --stage 2             themes + memo -> out/
  python -m scan status                    progress and errors
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from . import config, io_xlsx, pipeline


def main() -> None:
    ap = argparse.ArgumentParser(prog="scan", description="Portable Claude-API research scan.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="write a sample input/organizations.xlsx")
    st = sub.add_parser("status", help="show progress and errors")
    st.add_argument("--profile", default=None, help="scan profile (default horizon)")

    pr = sub.add_parser("prune", help="delete all but the newest run folders under runs/")
    pr.add_argument("--keep", type=int, default=20, help="how many runs to keep (default 20)")
    pr.add_argument("--dry-run", action="store_true", help="list what would go, delete nothing")

    ev = sub.add_parser("eval", help="trajectory eval on the golden set, and optionally judge a memo")
    ev.add_argument("--provider", choices=["anthropic", "openrouter", "claude-cli"], default=None)
    ev.add_argument("--model", default=None, help="openrouter model id")
    ev.add_argument("--judge", type=Path, default=None, help="path to a memo .md to score on the rubric")
    ev.add_argument("--profile", default=None, help="scan profile (default horizon)")
    ev.add_argument("--search", action="store_true",
                    help="with a profile: test whether the evidence search finds the golden evaluations")

    run = sub.add_parser("run", help="run a stage")
    run.add_argument("--stage", type=int, choices=[1, 2], required=True)
    run.add_argument("--only", type=Path, default=None,
                     help="stage 1 only: scan just the orgs in this xlsx (incremental)")
    run.add_argument("--dry-run", action="store_true",
                     help="mock every model call, no key or network needed")
    run.add_argument("--provider", choices=["anthropic", "openrouter", "claude-cli"], default=None,
                     help="which backend to run the agents on")
    run.add_argument("--model", default=None,
                     help="openrouter model id when --provider openrouter, e.g. openai/gpt-5")
    run.add_argument("--scope", choices=["africa", "global"], default=None,
                     help="africa focus (default) or a global scan")
    run.add_argument("--profile", default=None,
                     help="scan profile under profiles/, e.g. yes (default: the horizon scan)")
    run.add_argument("--roster", type=Path, default=None,
                     help="organization sheet to use instead of the profile's own, e.g. a pilot list")

    args = ap.parse_args()
    config.use_profile(getattr(args, "profile", None))

    if args.cmd == "init":
        p = io_xlsx.write_sample_orgs()
        print(f"wrote {p}. Edit it, then: python -m scan run --stage 1")
        return
    if args.cmd == "status":
        pipeline.status()
        return
    if args.cmd == "prune":
        gone = pipeline.prune_runs(keep=args.keep, dry=args.dry_run)
        verb = "would remove" if args.dry_run else "removed"
        print(f"{verb} {len(gone)} run folder(s), keeping the newest {args.keep}")
        for name in gone:
            print(f"  {name}")
        return
    if args.cmd == "eval":
        if args.provider:
            config.PROVIDER = args.provider
        if args.model:
            config.OR_MODEL = args.model
        config.require_key()
        from . import evaluate
        golden = config.PROFILES_DIR / (args.profile or "") / "golden.json"
        if args.profile and config.active_spec().get("evidence") and golden.exists():
            if args.search:
                res = asyncio.run(evaluate.search_recall(golden))
                report, out = evaluate.recall_report(res), config.REVIEW_DIR / "search_recall.md"
            else:
                res = asyncio.run(evaluate.evidence_eval(golden))
                report, out = evaluate.evidence_report(res), config.REVIEW_DIR / "evidence_accuracy.md"
            out.write_text(report, encoding="utf-8")
            print(report)
            print(f"written to {out}")
            if not res["passed"]:
                raise SystemExit(1)
            return
        rows = asyncio.run(evaluate.trajectory())
        evaluate.print_trajectory(rows)
        if args.judge:
            res = asyncio.run(evaluate.judge_memo(args.judge.read_text(encoding="utf-8")))
            evaluate.print_rubric(res)
        return
    if args.cmd == "run":
        if getattr(args, "dry_run", False):
            config.DRY_RUN = True
            print("[dry-run] mocking all model calls, no API key or network used\n")
        if args.provider:
            config.PROVIDER = args.provider
        if args.model:
            config.OR_MODEL = args.model
        if args.scope:
            config.SCAN_MODE = args.scope
        if args.roster:
            config.ORG_SHEET = args.roster
        if config.PROVIDER == "openrouter" and not config.DRY_RUN:
            print(f"[openrouter] running every stage on {config.OR_MODEL}\n")
        config.require_key()
        if not config.ORG_SHEET.exists() and not args.only:
            raise SystemExit(f"{config.ORG_SHEET} missing. Run: python -m scan init")
        if args.stage == 1:
            asyncio.run(pipeline.run_stage1(only=args.only))
        else:
            asyncio.run(pipeline.run_stage2())


if __name__ == "__main__":
    main()
