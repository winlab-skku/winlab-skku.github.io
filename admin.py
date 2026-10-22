#!/usr/bin/env python3
"""WIn Lab admin — local editing page with GitHub sync and one-click deploy.

    WInLabAdmin.exe            (or: python admin.py)

1. On start it pulls the latest version of the repository from GitHub into this folder.
   Files you changed here but have not deployed yet are kept. If someone else deployed a
   change to the same file, their version wins and yours is copied to _backup/<time>/ first.
2. It opens http://localhost:8765/admin/ for editing. "저장 + 빌드" writes data/*.json and docs/.
3. "GitHub에 배포" commits every changed file straight to the repository through the GitHub API.
   That needs a personal access token, saved once on this PC (outside this folder, never uploaded).

The server listens on 127.0.0.1 only. Nothing here works from the published site.
"""
import base64, datetime, hashlib, importlib, importlib.util, json, os, platform, re, shutil, sys, threading, traceback
import html as htmllib
import urllib.error, urllib.parse, urllib.request, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

OWNER, REPO, BRANCH = "winlab-skku", "winlab-skku.github.io", "main"
SITE_URL = f"https://{REPO}/" if REPO.endswith(".github.io") else f"https://{OWNER}.github.io/{REPO}/"
PORT = 8765
STATE_FILE = ".sync-state.json"     # what this folder last matched on GitHub (local only)
BACKUP_DIR = "_backup"              # local copies kept before GitHub versions replace them
LOCAL_ONLY = {"MANUAL.md"}          # kept in this folder only: never uploaded, never touched by sync
API = os.environ.get("WINLAB_GITHUB_API", "https://api.github.com")
RAW = os.environ.get("WINLAB_GITHUB_RAW", "https://raw.githubusercontent.com")


def default_root():
    return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


# ================================================================ files

def ignored(path):
    """Paths that are never synced or deployed: local-only state, build leftovers, and binaries
    (a running .exe cannot be overwritten on Windows, and a 17 MB upload per deploy is wasteful)."""
    parts = path.split("/")
    name = parts[-1]
    if len(parts) == 1 and name in LOCAL_ONLY:
        return True
    if parts[0] in ("build", "dist", BACKUP_DIR) and len(parts) > 1:
        return True
    if any(p in (".git", "__pycache__", ".venv", "venv", "node_modules") for p in parts):
        return True
    if name in (STATE_FILE, ".DS_Store", "Thumbs.db", "desktop.ini", "WInLabAdmin"):
        return True
    if name.lower().endswith((".exe", ".spec", ".pyc", ".tmp-winlab")) or name.startswith("~$"):
        return True
    return False


def git_blob_sha(data):
    """The id git (and GitHub) gives a file's content, so local and remote files compare without downloading."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def local_path(root, path):
    return os.path.join(root, *path.split("/"))


def scan_local(root):
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        dirnames[:] = sorted(d for d in dirnames if not ignored(f"{rel}/{d}/x" if rel else f"{d}/x"))
        for f in filenames:
            p = f"{rel}/{f}" if rel else f
            if ignored(p):
                continue
            with open(os.path.join(dirpath, f), "rb") as fh:
                files[p] = git_blob_sha(fh.read())
    return files


def read_bytes(root, path):
    with open(local_path(root, path), "rb") as f:
        return f.read()


def write_bytes(root, path, data):
    dst = local_path(root, path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tmp-winlab"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)


def remove_file(root, path):
    p = local_path(root, path)
    if os.path.exists(p):
        os.remove(p)
    d = os.path.dirname(p)                       # tidy up folders the deletion emptied
    while os.path.abspath(d) != os.path.abspath(root) and os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
        d = os.path.dirname(d)


def backup(root, path, stamp):
    src = local_path(root, path)
    if os.path.exists(src):
        dst = os.path.join(root, BACKUP_DIR, stamp, *path.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def now_stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_state(root):
    try:
        with open(os.path.join(root, STATE_FILE), encoding="utf-8") as f:
            s = json.load(f)
        if s.get("repo") == f"{OWNER}/{REPO}" and isinstance(s.get("files"), dict) and s.get("base"):
            return s
    except (OSError, ValueError):
        pass
    return None


def save_state(root, head, files):
    state = {"repo": f"{OWNER}/{REPO}", "base": head["sha"], "head": head, "files": files,
             "synced_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    write_bytes(root, STATE_FILE, json.dumps(state, ensure_ascii=False, indent=1).encode("utf-8"))
    return state


def pending_changes(root):
    """Files that differ from the GitHub version this folder last synced with (= what a deploy would upload)."""
    state = load_state(root)
    if state is None:
        return None
    local, base = scan_local(root), state["files"]
    return [{"path": p, "kind": "added" if p not in base else "deleted" if p not in local else "modified"}
            for p in sorted(set(local) | set(base)) if local.get(p) != base.get(p)]


# ================================================================ token (stored per PC, outside the project)

def token_file():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "WInLabAdmin", "github-token.json")


def load_token():
    try:
        with open(token_file(), encoding="utf-8") as f:
            t = json.load(f)
        return t if t.get("token") else None
    except (OSError, ValueError):
        return None


def save_token(token, login):
    p = token_file()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"token": token, "login": login, "repo": f"{OWNER}/{REPO}"}, f)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def clear_token():
    try:
        os.remove(token_file())
    except OSError:
        pass


# ================================================================ GitHub API

class GitHubError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class GitHub:
    def __init__(self, token=None):
        self.token = token

    def _open(self, url, method="GET", body=None, accept="application/vnd.github+json", auth=True):
        headers = {"Accept": accept, "User-Agent": "WInLabAdmin", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token and auth:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("message", detail)
            except ValueError:
                pass
            raise GitHubError(e.code, detail) from None
        except (urllib.error.URLError, OSError) as e:
            raise GitHubError(0, f"GitHub에 연결할 수 없습니다 ({getattr(e, 'reason', e)})") from None

    def call(self, method, path, body=None):
        raw = self._open(f"{API}/repos/{OWNER}/{REPO}{path}", method, body)
        return json.loads(raw) if raw else None

    def user(self):
        return json.loads(self._open(f"{API}/user"))

    def head(self):
        c = self.call("GET", f"/commits/{BRANCH}")
        info = c["commit"]
        return {"sha": c["sha"], "tree": info["tree"]["sha"],
                "message": (info.get("message") or "").splitlines()[0] if info.get("message") else "",
                "author": (c.get("author") or {}).get("login") or info["author"]["name"],
                "date": info["author"]["date"]}

    def tree(self, tree_sha):
        t = self.call("GET", f"/git/trees/{tree_sha}?recursive=1")
        if t.get("truncated"):
            raise GitHubError(0, "저장소 파일 목록이 너무 커서 한 번에 받을 수 없습니다.")
        return {e["path"]: e["sha"] for e in t["tree"]
                if e["type"] == "blob" and e.get("mode") != "120000" and not ignored(e["path"])}

    def download(self, commit, path, sha):
        data = None
        try:   # raw.githubusercontent.com does not count against the API rate limit
            data = self._open(f"{RAW}/{OWNER}/{REPO}/{commit}/{urllib.parse.quote(path)}", accept="*/*", auth=False)
        except GitHubError:
            pass
        if data is None or git_blob_sha(data) != sha:
            data = base64.b64decode(self.call("GET", f"/git/blobs/{sha}")["content"])
        if git_blob_sha(data) != sha:
            raise GitHubError(0, f"받은 파일이 손상되었습니다: {path}")
        return data


def friendly(e, writing=False):
    """Turn a GitHubError into something a lab member can act on."""
    msg = str(e)
    if e.status == 401:
        return "GitHub 토큰이 만료되었거나 잘못되었습니다. GitHub 탭에서 새 토큰으로 다시 연결하세요."
    if e.status in (403, 429) and "rate limit" in msg.lower():
        return "GitHub 요청 한도(토큰 없이 시간당 60회)를 넘었습니다. 잠시 후 다시 시도하거나 GitHub 탭에서 토큰을 연결하세요."
    if writing and e.status in (403, 404):
        return (f"이 토큰으로는 저장소에 쓸 수 없습니다. 토큰의 Repository access에 {REPO}가 있고 Contents가 "
                f"Read and write인지, 조직 승인 대기 중은 아닌지 확인하세요. (GitHub: {msg})")
    if e.status == 404:
        return f"GitHub에서 {OWNER}/{REPO} 저장소를 찾을 수 없습니다. (GitHub: {msg})"
    return msg if e.status == 0 else f"GitHub 오류 {e.status}: {msg}"


# ================================================================ sync

def classify(local, remote, base):
    """Three-way comparison per file. L=this folder, R=GitHub now, B=GitHub when this folder last synced."""
    take, conflicts, pending = [], [], []
    for p in sorted(set(local) | set(remote) | set(base)):
        L, R, B = local.get(p), remote.get(p), base.get(p)
        if L == R:
            continue
        if L == B:
            take.append(p)          # only GitHub changed it
        elif R == B:
            pending.append(p)       # only changed here: keep, deploy later
        else:
            conflicts.append(p)     # changed on both sides
    return take, conflicts, pending


def sync(root, gh, mode="auto", on_conflict="remote"):
    """Bring this folder up to date with GitHub.

    mode="auto":        three-way update; local-only changes are kept.
    mode="take-remote": make this folder identical to GitHub (differences are backed up first).
    mode="keep-local":  first run only — accept this folder as is; differences become pending changes.
    on_conflict="remote" replaces conflicting files with GitHub's version (local copy backed up);
    on_conflict="abort" changes nothing and reports the conflicting files (used before a deploy).
    """
    state = load_state(root)
    if mode == "keep-local" and state is not None:
        mode = "auto"                     # keep-local is only meaningful before the first sync
    head = gh.head()
    if state and state["base"] == head["sha"] and mode == "auto":
        remote = state["files"]           # GitHub has not moved since the last sync
    else:
        remote = gh.tree(head["tree"])
    local = scan_local(root)
    report = {"ok": True, "head": head, "updated": [], "deleted": [], "conflicts": [], "backup": None,
              "first_run": False, "remote_moved": bool(state) and state["base"] != head["sha"]}

    if mode == "auto" and state is None:
        diffs = [p for p in sorted(set(local) | set(remote)) if local.get(p) != remote.get(p)]
        if diffs:   # never guess on the first run: the user decides which side is right
            report["first_run"] = True
            report["diffs"] = [{"path": p, "kind": "local-only" if p not in remote else
                                "remote-only" if p not in local else "different"} for p in diffs]
            return report
        save_state(root, head, remote)
        return report
    if mode == "keep-local":
        save_state(root, head, remote)
        return report
    if mode == "take-remote":
        take, conflicts = [], [p for p in sorted(set(local) | set(remote)) if local.get(p) != remote.get(p)]
    else:
        take, conflicts, _ = classify(local, remote, state["files"])

    if conflicts and on_conflict == "abort":
        report.update(ok=False, conflicts=conflicts)
        return report
    if conflicts:
        stamp = now_stamp()
        for p in conflicts:
            backup(root, p, stamp)
        report["backup"] = f"{BACKUP_DIR}/{stamp}"
        report["conflicts"] = conflicts
    for p in take + conflicts:
        if p in remote:
            write_bytes(root, p, gh.download(head["sha"], p, remote[p]))
            report["updated"].append(p)
        else:
            remove_file(root, p)
            report["deleted"].append(p)
    save_state(root, head, remote)
    return report


def safe_sync(root, mode="auto"):
    """Sync for startup / the '최신 받기' button: never raises, falls back to working offline."""
    tok = load_token()
    try:
        try:
            rep = sync(root, GitHub(tok["token"] if tok else None), mode)
        except GitHubError as e:
            if e.status != 401 or not tok:
                raise
            rep = sync(root, GitHub(None), mode)        # public repo: reading works without the token
            rep["token_invalid"] = True
        return rep
    except GitHubError as e:
        return {"ok": False, "offline": e.status == 0, "error": friendly(e)}
    except Exception as e:  # keep the admin usable whatever happens
        traceback.print_exc()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ================================================================ deploy

def deploy(root, token, message, rebuild):
    """Commit every changed file to GitHub in one commit. Pulls others' non-overlapping changes first."""
    gh = GitHub(token)
    if load_state(root) is None:
        return {"ok": False, "code": "no-state", "error": "먼저 GitHub과 동기화해야 합니다 (화면 위의 첫 동기화 안내를 따라주세요)."}
    pre = sync(root, gh, "auto", on_conflict="abort")
    if not pre["ok"]:
        return {"ok": False, "code": "conflict", "files": pre["conflicts"],
                "error": "다른 사람이 같은 파일을 먼저 배포했습니다."}
    pulled = pre["updated"] + pre["deleted"]
    if pulled:
        rebuild()        # combine their changes with ours so the uploaded pages match the merged data
    state = load_state(root)
    head, base, local = state["head"], state["files"], scan_local(root)
    changed = [p for p in sorted(set(local) | set(base)) if local.get(p) != base.get(p)]
    if not changed:
        return {"ok": True, "nothing": True, "pulled": pulled}
    entries = []
    for p in changed:
        if p in local:
            data = read_bytes(root, p)
            blob = gh.call("POST", "/git/blobs", {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
            entries.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        else:
            entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})   # deletion
    tree = gh.call("POST", "/git/trees", {"base_tree": head["tree"], "tree": entries})
    commit = gh.call("POST", "/git/commits", {"message": message, "tree": tree["sha"], "parents": [head["sha"]]})
    try:
        gh.call("PATCH", f"/git/refs/heads/{BRANCH}", {"sha": commit["sha"], "force": False})
    except GitHubError as e:
        if e.status == 422:
            return {"ok": False, "code": "raced", "error": "방금 다른 배포가 먼저 끝났습니다. 다시 배포를 눌러주세요."}
        raise
    files = dict(base)
    for p in changed:
        if p in local:
            files[p] = local[p]
        else:
            files.pop(p, None)
    login = (load_token() or {}).get("login") or ""
    new_head = {"sha": commit["sha"], "tree": tree["sha"], "message": message.splitlines()[0], "author": login,
                "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    save_state(root, new_head, files)
    return {"ok": True, "commit": commit["sha"], "files": changed, "pulled": pulled,
            "commit_url": f"https://github.com/{OWNER}/{REPO}/commit/{commit['sha']}", "site_url": SITE_URL}


# ================================================================ professor's CV site → publications

CV_URL = "https://sites.google.com/view/kisonglee/publications"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
_BLOCK_TAGS = re.compile(r"<\s*/?\s*(?:p|div|li|ul|ol|h[1-6]|br|hr|tr|td|th|table|section|article|header|footer|nav|main|blockquote)\b[^>]*>", re.I)
_SECTION = re.compile(r"^(?:under review|early access|in press|accepted|\d{4}(?:\s*(?:and|&)\s*(?:before|earlier|prior))?)$", re.I)
_STOP = re.compile(r"\b(?:journals?|conferences?|proceedings|patents?|books?|workshops?|talks?|awards?|honors?|projects?)\b", re.I)
_PAPER = re.compile(r'^(?P<authors>.+?)\s*,?\s*[“"](?P<title>.+?)\s*,?\s*[”"]\s*,?\s*(?P<rest>.*)$')


def fetch_cv(url):
    if not re.match(r"^https?://", url or ""):
        raise ValueError("CV 주소는 https:// 로 시작해야 합니다.")
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9,ko;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise ValueError(f"CV 페이지를 열 수 없습니다 (HTTP {e.code}). 주소가 맞는지, 페이지가 공개 상태인지 확인하세요.") from None
    except (urllib.error.URLError, OSError) as e:
        raise ValueError(f"CV 페이지에 연결할 수 없습니다 ({getattr(e, 'reason', e)}). 인터넷 연결을 확인하세요.") from None


def html_to_text(page):
    """Google Sites HTML → one line per paragraph / list item / heading (inline formatting dropped)."""
    page = re.sub(r"<(script|style|noscript|svg|template)\b.*?</\1\s*>", " ", page, flags=re.I | re.S)
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    page = _BLOCK_TAGS.sub("\n", page)
    page = re.sub(r"<[^>]+>", "", page)
    return htmllib.unescape(page)


def _clean(line):
    line = re.sub(r"\[#h\.[^\]]*\]\([^)]*\)", "", line)       # anchor links when the page was copied as markdown
    line = re.sub(r"#h\.[0-9a-z]+", "", line, flags=re.I)      # Google Sites heading anchors
    line = re.sub(r"[\s ​‎﻿]+", " ", line).strip()
    line = re.sub(r"^#+\s*", "", line)                         # markdown heading marks
    line = re.sub(r"^\d+[.)]\s+", "", line)                    # list numbers from a copy/paste
    return line


def parse_cv_text(text):
    """CV page text → {"sections": [...], "items": [{section, authors, title, venue, meta}]}.
    Starts at the first section heading (Under Review / Early Access / a year / 'YYYY and Before') and
    stops at the next non-paper heading such as 'Conferences' or 'Patents', so other lists are never mixed in."""
    sections, items, seen = [], [], set()
    cur, carry = None, ""
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue
        if carry:                       # a paper whose title was split over two lines
            line, carry = carry + " " + line, ""
        if _SECTION.match(line):
            cur = line
            if cur not in sections:
                sections.append(cur)
            continue
        if cur is None:
            continue
        if line.count("“") > line.count("”"):
            carry = line
            continue
        m = _PAPER.match(line)
        if m:
            authors = re.sub(r"\*\s+", "*", m.group("authors")).strip(" ,")
            title = m.group("title").strip(" ,")
            rest, meta = m.group("rest").strip(), ""
            mm = re.match(r"^(.*?)\s*\((IF[^()]*)\)\s*\.?$", rest)
            if mm:
                rest, meta = mm.group(1), mm.group(2).strip()
            key = pub_key(title)
            if key and key not in seen:
                seen.add(key)
                items.append({"section": cur, "authors": authors, "title": title, "venue": rest.strip(" ,"), "meta": meta})
            continue
        if line.startswith("(IF") and items and not items[-1]["meta"]:     # IF note on its own line
            items[-1]["meta"] = line.strip("() ")
            continue
        if _STOP.search(line) and len(line) < 80:
            break                       # e.g. "Conferences", "Domestic Journals": a different list starts
    sections = [s for s in sections if any(i["section"] == s for i in items)]
    return {"sections": sections, "items": items}


def pub_key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def diff_pubs(cur, new):
    """What applying `new` would change in `cur`, matched by title."""
    ci = {pub_key(i["title"]): i for i in cur.get("items", [])}
    ni = {pub_key(i["title"]): i for i in new["items"]}
    added = [i for k, i in ni.items() if k not in ci]
    removed = [i for k, i in ci.items() if k not in ni]
    changed = []
    for k, n in ni.items():
        c = ci.get(k)
        if c:
            fields = [{"field": f, "old": c.get(f) or "", "new": n.get(f) or ""}
                      for f in ("section", "authors", "title", "venue", "meta") if (c.get(f) or "") != (n.get(f) or "")]
            if fields:
                changed.append({"title": n["title"], "fields": fields})
    order = [pub_key(i["title"]) for i in cur.get("items", [])] != [pub_key(i["title"]) for i in new["items"]]
    reordered = order and not added and not removed and not any(
        f["field"] == "section" for c in changed for f in c["fields"])
    counts = {s: sum(1 for i in new["items"] if i["section"] == s) for s in new["sections"]}
    same = not added and not removed and not changed and not order and cur.get("sections") == new["sections"]
    return {"added": added, "removed": removed, "changed": changed, "reordered": reordered, "same": same,
            "counts": counts, "total": len(new["items"]), "current_total": len(cur.get("items", []))}


# ================================================================ local server

def load_module(root, name):
    """Load name.py from the project folder (so synced code updates apply without rebuilding the exe);
    fall back to the copy bundled in the exe if the file is missing or broken."""
    path = os.path.join(root, name + ".py")
    if os.path.exists(path):
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            traceback.print_exc()
            print(f"[!] {name}.py could not be loaded; using the built-in copy.")
            sys.modules.pop(name, None)
    return importlib.import_module(name)


def load_build(root):
    b = load_module(root, "build")
    b.ROOT = root
    b.SITE = os.path.join(root, "docs")
    b.DATA = os.path.join(root, "data")
    b.SITE_JSON = os.path.join(b.DATA, "site.json")
    b.PUBS_JSON = os.path.join(b.DATA, "publications.json")
    return b


class Ctx:
    def __init__(self, root, report):
        self.root = root
        self.site = os.path.join(root, "docs")
        self.data = os.path.join(root, "data")
        self.report = report
        self.build = load_build(root)
        self.lock = threading.Lock()
        self.port = PORT


CTX = None


def read_json(name):
    with open(os.path.join(CTX.data, name), encoding="utf-8") as f:
        return json.load(f)


def write_json(name, data):
    with open(os.path.join(CTX.data, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def status():
    tok = load_token()
    state = load_state(CTX.root)
    host = platform.node() or "PC"
    return {"repo": f"{OWNER}/{REPO}", "branch": BRANCH, "site_url": SITE_URL,
            "head": state["head"] if state else None, "synced_at": state["synced_at"] if state else None,
            "pending": pending_changes(CTX.root), "report": CTX.report,
            "login": tok.get("login") if tok else None, "token_file": token_file(),
            "token_name": f"WInLab admin ({host})"[:40]}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=CTX.site, **kw)   # "/" serves the built site (preview)

    def translate_path(self, path):
        p = urllib.parse.urlparse(path).path
        if p == "/admin" or p.startswith("/admin/"):     # the editor itself lives in ./admin
            rel = urllib.parse.unquote(p[len("/admin"):].lstrip("/")) or "index.html"
            full = os.path.normpath(os.path.join(CTX.root, "admin", rel))
            return full if full.startswith(os.path.join(CTX.root, "admin")) else os.path.join(CTX.root, "admin", "index.html")
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        if args and "/api/" in str(args[0]):
            super().log_message(fmt, *args)

    def log_error(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def allowed(self, post):
        """Only this machine's own admin page may call the API. Blocks other websites open in the
        browser (cross-site requests) and DNS-rebinding tricks from reaching the deploy token."""
        hosts = {f"localhost:{CTX.port}", f"127.0.0.1:{CTX.port}"}
        if self.headers.get("Host", "") not in hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in hosts}:
            return False
        if post and not self.headers.get("Content-Type", "").startswith("application/json"):
            return False
        return True

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            if not self.allowed(False):
                return self.send_json({"ok": False, "error": "forbidden"}, 403)
            if path == "/api/data":
                return self.send_json({"ok": True, "site": read_json("site.json"), "pubs": read_json("publications.json"),
                                       "root": CTX.root, "cv_url": CV_URL,
                                       "photos": sorted(os.listdir(os.path.join(CTX.site, "assets/photos"))),
                                       "research_images": sorted(os.listdir(os.path.join(CTX.site, "assets/research")))})
            if path == "/api/status":
                return self.send_json({"ok": True, **status()})
            return self.send_json({"ok": False, "error": "unknown endpoint"}, 404)
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not self.allowed(True):
            return self.send_json({"ok": False, "error": "forbidden"}, 403)
        try:
            d = self.read_body()
            if path == "/api/save":
                with CTX.lock:
                    write_json("site.json", d["site"])
                    write_json("publications.json", d["pubs"])
                    written = CTX.build.build() if d.get("build", True) else []
                return self.send_json({"ok": True, "written": written})
            if path == "/api/build":
                with CTX.lock:
                    written = CTX.build.build()
                return self.send_json({"ok": True, "written": written})
            if path == "/api/upload":
                folder = "assets/photos" if d.get("kind") == "photo" else "assets/research"
                name = os.path.basename(d["name"])
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    return self.send_json({"ok": False, "error": "jpg/png only"}, 400)
                with open(os.path.join(CTX.site, folder, name), "wb") as f:
                    f.write(base64.b64decode(d["data"].split(",")[-1]))
                return self.send_json({"ok": True, "path": f"{folder}/{name}"})
            if path == "/api/delete-photo":
                p = os.path.join(CTX.site, "assets/photos", os.path.basename(d["name"]))
                if os.path.exists(p):
                    os.remove(p)
                return self.send_json({"ok": True})
            if path == "/api/sync":
                with CTX.lock:
                    rep = safe_sync(CTX.root, d.get("mode", "auto"))
                    CTX.report = rep
                    CTX.build = load_build(CTX.root)       # pick up a build.py that just arrived
                    rebuild_after_sync(rep)
                return self.send_json({"ok": rep.get("ok", False), "report": rep, "error": rep.get("error")})
            if path == "/api/token":
                token = (d.get("token") or "").strip()
                if not token:
                    clear_token()
                    return self.send_json({"ok": True, "login": None})
                gh = GitHub(token)
                try:
                    login = gh.user()["login"]
                    repo = gh.call("GET", "")
                except GitHubError as e:
                    return self.send_json({"ok": False, "error": friendly(e)})
                save_token(token, login)
                warn = None
                if (repo.get("permissions") or {}).get("push") is False:
                    warn = f"@{login} 계정에 이 저장소 쓰기 권한이 없습니다. 조직(winlab-skku) 멤버로 초대받아야 배포할 수 있습니다."
                return self.send_json({"ok": True, "login": login, "warning": warn})
            if path == "/api/cv-import":
                try:
                    if (d.get("text") or "").strip():
                        text, source = d["text"], "붙여넣은 내용"
                    else:
                        source = (d.get("url") or CV_URL).strip()
                        text = html_to_text(fetch_cv(source))
                except ValueError as e:
                    return self.send_json({"ok": False, "error": str(e)})
                parsed = parse_cv_text(text)
                if not parsed["items"]:
                    return self.send_json({"ok": False, "error": "CV 페이지에서 논문 목록을 찾지 못했습니다. 주소가 Publications 페이지가 맞는지 확인하세요. "
                                                                 "계속 안 되면 '직접 붙여넣기'를 사용하세요."})
                return self.send_json({"ok": True, "source": source, "pubs": parsed,
                                       "diff": diff_pubs(d.get("current") or {}, parsed)})
            if path == "/api/deploy":
                tok = load_token()
                if not tok:
                    return self.send_json({"ok": False, "code": "no-token", "error": "GitHub 탭에서 토큰을 먼저 연결하세요."})
                message = (d.get("message") or "").strip() or "Update site"
                with CTX.lock:
                    try:
                        res = deploy(CTX.root, tok["token"], message, CTX.build.build)
                    except GitHubError as e:
                        res = {"ok": False, "code": f"http-{e.status}", "error": friendly(e, writing=True)}
                    CTX.build = load_build(CTX.root)
                return self.send_json(res)
            return self.send_json({"ok": False, "error": "unknown endpoint"}, 404)
        except Exception as e:  # show the error in the page instead of dying
            traceback.print_exc()
            return self.send_json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


def describe(rep):
    if not rep.get("ok"):
        return "  [!] " + (rep.get("error") or "GitHub 동기화 실패") + " — 이 폴더의 파일로 작업합니다."
    h = rep["head"]
    lines = [f"  GitHub 최신: {h['sha'][:7]} \"{h['message']}\" ({h['author']}, {h['date'][:10]})"]
    if rep.get("first_run"):
        lines.append(f"  첫 실행: 이 폴더와 GitHub이 {len(rep['diffs'])}개 파일에서 다릅니다. 관리자 화면에서 어느 쪽을 쓸지 고르세요.")
    n = len(rep["updated"]) + len(rep["deleted"])
    if n:
        lines.append(f"  GitHub에서 {n}개 파일을 받아왔습니다.")
    if rep["conflicts"]:
        lines.append(f"  [!] 겹친 파일 {len(rep['conflicts'])}개는 GitHub 버전으로 바꾸고 내 버전은 {rep['backup']}/ 에 보관했습니다.")
    if not n and not rep.get("first_run"):
        lines.append("  이미 최신 상태입니다.")
    return "\n".join(lines)


def rebuild_after_sync(rep):
    """Pages are generated from data/: after pulling anything, rebuild so docs/ matches the data now here.
    (Builds are byte-for-byte reproducible, so this adds no changes when GitHub's pages were already current.)"""
    if rep.get("ok") and (rep.get("updated") or rep.get("deleted")):
        try:
            CTX.build.build()
        except Exception:
            traceback.print_exc()


def serve(root, report):
    global CTX
    CTX = Ctx(root, report)
    rebuild_after_sync(report)
    server = None
    for port in range(PORT, PORT + 10):   # another admin window may still be open: use the next port
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            print(f"Port {port} is in use (another admin window is probably open) - trying {port + 1}")
    if server is None:
        print("Could not open a port. Close other admin windows and try again.")
        input("Press Enter to exit.")
        sys.exit(1)
    CTX.port = port
    url = f"http://localhost:{port}/admin/"
    print(f"\n  Admin page:   {url}\n  Site preview: http://localhost:{port}/\n\nClose this window (or press Ctrl+C) to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main(root=None):
    root = os.path.abspath(root or default_root())
    for need in ("admin/index.html", "data/site.json", "data/publications.json", "docs/assets/style.css"):
        if not os.path.exists(os.path.join(root, need)):
            print(f"'{need}' not found next to this program. Put WInLabAdmin.exe (or admin.py) in the website "
                  f"folder (next to data/ and docs/) and run it again.")
            input("Press Enter to exit.")
            sys.exit(1)
    print(f"WIn Lab admin — {root}\nGitHub({OWNER}/{REPO})에서 최신 버전을 확인하는 중…")
    report = safe_sync(root)
    print(describe(report))
    if "admin.py" in report.get("updated", []):     # a newer admin.py just arrived: run that one
        try:
            return load_module(root, "admin").serve(root, report)
        except Exception:
            traceback.print_exc()
    return serve(root, report)


if __name__ == "__main__":
    main(default_root())
