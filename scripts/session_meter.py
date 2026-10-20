"""Local explicit checkpoints; no background hooks or model API calls."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def count(text, encoding):
    if encoding == "characters":
        return len(text)
    try:
        import tiktoken
    except ImportError:
        raise SystemExit("tiktoken unavailable: use --metric characters at init; do not label characters as tokens")
    return len(tiktoken.get_encoding(encoding).encode(text, disallowed_special=()))


def events(root):
    p = root / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x] if p.exists() else []


def event_kind(event):
    # Preserve old files verbatim while excluding known v2 archive-control replies.
    return event.get("kind", "control" if event["key"].startswith("assistant-archive-") else "task")


def append_event(root, state, rows, role, file, key, kind="task"):
    data = file.resolve().read_bytes()
    body = data.decode("utf-8-sig").replace("\r\n", "\n")
    existing = next((e for e in rows if e["key"] == key), None)
    if existing:
        if existing["sha256"] != digest(data) or existing["role"] != role or event_kind(existing) != kind:
            raise SystemExit("Duplicate key with changed content, role or kind")
        return
    event_id = len(rows) + 1
    raw = root / "raw"
    raw.mkdir(exist_ok=True)
    stored = raw / (str(event_id).zfill(5) + ".txt")
    stored.write_bytes(data)
    e = {"id": event_id, "key": key, "role": role, "kind": kind, "at": now(),
         "source": str(file.resolve()), "stored": str(stored.relative_to(root)),
         "sha256": digest(data), "characters": len(body), "units": count(body, state["metric"])}
    with (root / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    rows.append(e)


def status(root, state, rows):
    pending = [e for e in rows if e["id"] > state["archived_through"]]
    rounds = sum(e["role"] == "assistant" and event_kind(e) == "task" for e in rows)
    new_rounds = rounds - state["checkpoint_round"]
    units = sum(e["units"] for e in pending)
    return {
        "scope": "explicitly recorded visible messages/materials, not host active context",
        "metric": state["metric"], "threshold": state["threshold"],
        "completed_rounds": rounds, "checkpoint_due": new_rounds >= state["every"],
        "unarchived_units": units, "threshold_reached": units >= state["threshold"],
        "archive_suggested": new_rounds >= state["every"] and units >= state["threshold"],
        "cumulative_units": sum(e["units"] for e in rows),
        "cumulative_characters": sum(e["characters"] for e in rows),
        "unarchived_events": len(pending), "last_archive": state.get("last_archive"),
        "approval_pending": state.get("approval") is not None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--every", type=int, default=10)
    init.add_argument("--threshold", type=int, default=30000)
    init.add_argument("--metric", choices=["o200k_base", "cl100k_base", "characters"], default="characters")
    log = sub.add_parser("record")
    log.add_argument("--role", choices=["user", "assistant", "material"], required=True)
    log.add_argument("--file", type=Path, required=True)
    log.add_argument("--key", required=True, help="Unique ingestion ID; repeating identical ID is idempotent")
    log.add_argument("--kind", choices=["task", "control"], default="task")
    turn = sub.add_parser("record-turn")
    turn.add_argument("--user-file", type=Path, required=True)
    turn.add_argument("--assistant-file", type=Path, required=True)
    turn.add_argument("--key", required=True)
    turn.add_argument("--kind", choices=["task", "control"], default="task")
    sub.add_parser("status")
    sub.add_parser("checkpoint")
    approve = sub.add_parser("approve")
    approve.add_argument("--file", type=Path, required=True, help="Actual user approval message")
    approve.add_argument("--explicit-consent", action="store_true", help="Caller confirms alternate original wording explicitly authorizes this archive")
    archive = sub.add_parser("archive")
    archive.add_argument("--memory", type=Path, required=True)
    archive.add_argument("--explanation", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"
    if args.action == "init":
        if state_path.exists():
            raise SystemExit("Already initialized; existing records preserved")
        if args.every < 1 or args.threshold < 1:
            raise SystemExit("every and threshold must be positive")
        count("probe", args.metric)
        state = {"version": 3, "created": now(), "every": args.every,
                 "threshold": args.threshold, "metric": args.metric,
                 "archived_through": 0, "checkpoint_round": 0, "approval": None}
        write_json(state_path, state)
    else:
        state = read_json(state_path)
        if state.get("version", 2) < 3:
            # Old checkpoints used control replies and permitted off-cadence checks.
            # Keep their audit trail; start the strict cadence at business round zero.
            state["legacy_checkpoint_round"] = state["checkpoint_round"]
            state["checkpoint_round"] = 0
            state["version"] = 3
            state["cadence_policy"] = "task_rounds_only; checkpoints_only"
            write_json(state_path, state)
    rows = events(root)
    checkpoint_report = None
    if args.action == "record":
        append_event(root, state, rows, args.role, args.file, args.key, args.kind)
    elif args.action == "record-turn":
        append_event(root, state, rows, "user", args.user_file, "user-" + args.key, args.kind)
        append_event(root, state, rows, "assistant", args.assistant_file, "assistant-" + args.key, args.kind)
    elif args.action == "checkpoint":
        before = status(root, state, rows)
        if not before["checkpoint_due"]:
            raise SystemExit("Checkpoint not due. Do not summarize or archive outside the configured cadence; explicit migration is a separate user action.")
        checkpoint_report = before
        state["checkpoint_round"] = before["completed_rounds"]
        write_json(state_path, state)
        with (root / "checkpoints.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now(), **before}, ensure_ascii=False) + "\n")
    elif args.action == "approve":
        approval = args.file.resolve().read_text(encoding="utf-8-sig").strip()
        if approval != "好的，请帮我压缩" and not (approval and args.explicit_consent):
            raise SystemExit("For this explicit approval route provide the exact user message: 好的，请帮我压缩")
        approval_key = "consent-" + str(state["archived_through"]) + "-" + str(len(rows))
        if not (rows and rows[-1]["role"] == "user" and digest(args.file.resolve().read_bytes()) == rows[-1]["sha256"]):
            append_event(root, state, rows, "user", args.file, approval_key, "control")
        state["approval"] = {"at": now(), "text": approval, "through_event": len(rows)}
        write_json(state_path, state)
    elif args.action == "archive":
        approval = state.get("approval")
        if not approval:
            raise SystemExit("Archive requires recorded user approval; raw logs remain untouched")
        end = approval["through_event"]
        selected = [e for e in rows if state["archived_through"] < e["id"] <= end]
        if not selected:
            raise SystemExit("No approved new events to archive")
        # Validate artifacts before creating the immutable snapshot directory.
        memory = args.memory.resolve().read_bytes()
        explanation = args.explanation.resolve().read_bytes()
        if not memory.strip() or not explanation.strip():
            raise SystemExit("Memory and explanation must be nonempty")
        for e in selected:
            if digest((root / e["stored"]).read_bytes()) != e["sha256"]:
                raise SystemExit("Raw content integrity failure: " + e["stored"])
        batch = "batch-" + str(selected[0]["id"]).zfill(5) + "-" + str(end).zfill(5)
        target = root / "archives" / batch
        target.mkdir(parents=True, exist_ok=False)
        (target / "memory.md").write_bytes(memory)
        (target / "compression-notes.md").write_bytes(explanation)
        manifest = {"created": now(), "batch": batch, "approval": approval,
                    "metric": state["metric"], "events": selected,
                    "memory_sha256": digest(memory), "notes_sha256": digest(explanation),
                    "warning": "Summary is not lossless; original recorded text remains under raw/"}
        write_json(target / "manifest.json", manifest)
        state.update(archived_through=end, last_archive=batch, approval=None)
        write_json(state_path, state)
    result = status(root, state, rows)
    if checkpoint_report is not None:
        result["checkpoint_report"] = checkpoint_report
    if args.action in {"record", "record-turn"}:
        result = {k: result[k] for k in ["completed_rounds", "checkpoint_due"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
