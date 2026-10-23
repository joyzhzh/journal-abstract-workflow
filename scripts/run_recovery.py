"""Preserve completed derived outputs while allowing source-cache checkpoints."""
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

DERIVED_JOURNAL_FILES = (
    "records.csv", "records.jsonl.gz", "summary.json", "openalex.csv",
    "abstract_gaps.csv", "references.csv.gz",
)


def save_state(root, state):
    temporary = root / "run_state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / "run_state.json")


def restore(root, state):
    archive = root / state["archive"]
    if not archive.resolve().is_relative_to((root / ".history").resolve()):
        raise ValueError("invalid recovery archive path")
    for relative in state["protected_paths"]:
        current = root / relative
        if not current.resolve().is_relative_to(root.resolve()):
            raise ValueError("invalid recovery output path")
        prior = archive / "before" / relative
        if current.exists():
            failed = archive / "incomplete" / relative
            failed.parent.mkdir(parents=True, exist_ok=True)
            # Recovery is retryable after an interruption; never replace a prior archive.
            if failed.exists():
                failed = failed.with_name(failed.name + "-" + uuid4().hex)
            current.rename(failed)
        if prior.is_dir():
            shutil.copytree(prior, current)
        elif prior.is_file():
            current.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prior, current)
    state["status"] = "failed_restored"
    save_state(root, state)


def begin(root, journals):
    root = Path(root)
    state_path = root / "run_state.json"
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if previous.get("status") == "running":
            # The documented one-process rule is enforced when the host supports it.
            pid = previous.get("pid")
            if os.name == "posix" and isinstance(pid, int) and pid > 0:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    raise ValueError("another pipeline process may be using this output directory") from None
                else:
                    raise ValueError("another pipeline process is using this output directory")
            elif os.name != "posix":
                raise ValueError("an interrupted run needs recovery; see run_state.json and the retained .history snapshot")
            restore(root, previous)
    # User-authored reviews and notebooks must survive recovery, including edits
    # made after a process crashed. Only files written by pipeline stages roll back.
    protected = [f"data/{slug}/{name}" for slug in journals for name in DERIVED_JOURNAL_FILES]
    protected += ["data/journals_crossref.csv.gz", "data/summary.json", "run_manifest.json"]
    archive = Path(".history") / uuid4().hex
    for relative in protected:
        current, prior = root / relative, root / archive / "before" / relative
        if current.is_dir():
            shutil.copytree(current, prior)
        elif current.is_file():
            prior.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, prior)
    state = {"status": "running", "pid": os.getpid(), "archive": str(archive), "protected_paths": protected}
    save_state(root, state)
    return state
