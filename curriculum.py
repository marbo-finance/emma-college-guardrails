"""Emma API v0 — curriculum catalog layer (stdlib only).

A tenant (a partner product) owns a *catalog*: the closed set of levels, subjects
and pedagogical objectives its product exposes. The catalog is DATA, tenant-
scoped and storage-independent. When a `/v1/chat` call references an objective
(via `child_context.v1.learning_context`), Emma resolves it against the
tenant's catalog and injects ONLY fixed-template lines built from catalog-
validated values into the system prompt — never raw client text.

SECURITY POSTURE (the safety layer is sovereign):
    - The catalog is tenant-owned but can NEVER weaken a child-safety gate.
      A catalog containing a "policy" key (anywhere) is REJECTED at load time.
      Nothing on the catalog path touches tenant policy flags.
    - Every string in a catalog is validated against a safe charset AT LOAD
      TIME (fail fast, same philosophy as api._load_tenants). Values later
      interpolated into the system prompt therefore cannot smuggle newlines or
      instruction-like control text.
    - Tenant isolation: a provider is asked for a catalog *id + version* that
      the caller (api.py) reads exclusively from the AUTHENTICATED tenant's
      config. The request body never selects a catalog, so one tenant can
      never read another tenant's catalog (confused-deputy safe by design).

Storage independence: `CurriculumCatalogProvider` is a duck-typed interface
(one method, `get_catalog(catalog_id, version) -> Catalog`). `FileCatalogProvider`
is the v0 implementation reading JSON files from a directory. A future DB- or
S3-backed provider drops in without touching api.py.
"""
import json
import os
import re

# --- safe patterns (validated at LOAD time; fail fast) ----------------------
# ids/versions: lowercase slug-ish, bounded.
_CATALOG_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_VERSION_RE = re.compile(r"^[0-9]{1,8}$")
_OBJECTIVE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
# level: short display token, e.g. "CM1", "6e". Letters/digits/space/._-
_LEVEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,31}$")
# subject: lowercase slug, e.g. "mathematics".
_SUBJECT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
# free display text (title / expected_notions). UNICODE \w covers accented
# letters; the class forbids [ ] { } < > newlines and every other control /
# injection-prone character. Bounded length.
_SAFE_TEXT_RE = re.compile(r"^[\w0-9 .,;:'’()\-°%/+&]{1,140}$", re.UNICODE)

_MAX_LEVELS = 64
_MAX_SUBJECTS = 64
_MAX_OBJECTIVES = 2000
_MAX_NOTIONS = 12


class CatalogError(Exception):
    """Base for catalog failures. api.py maps these to fail-closed HTTP codes."""


class CatalogNotFoundError(CatalogError):
    """No catalog file for the requested id+version."""


class CatalogValidationError(CatalogError):
    """A catalog file exists but is malformed / unsafe / policy-bearing."""


def _reject_policy_keys(node, where):
    """Recursively refuse any 'policy' key anywhere in the catalog. A tenant-
    owned catalog must never be able to carry (and thus attempt to override)
    child-safety policy flags."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "policy":
                raise CatalogValidationError(
                    f"catalog {where}: forbidden 'policy' key — catalogs may "
                    "never carry policy flags")
            _reject_policy_keys(v, where)
    elif isinstance(node, list):
        for v in node:
            _reject_policy_keys(v, where)


def _safe_text(v, field):
    if not isinstance(v, str) or not _SAFE_TEXT_RE.match(v):
        raise CatalogValidationError(f"catalog: {field} is not safe display text")
    return v


class Catalog:
    """A validated, read-only catalog. All strings passed load-time validation,
    so callers can interpolate `title`/level/notions into fixed templates
    without re-sanitizing."""

    def __init__(self, data, source):
        if not isinstance(data, dict):
            raise CatalogValidationError(f"{source}: catalog root must be an object")
        _reject_policy_keys(data, source)

        cv = data.get("catalog_version")
        if not isinstance(cv, str) or not _VERSION_RE.match(cv):
            raise CatalogValidationError(f"{source}: catalog_version must match ^[0-9]{{1,8}}$")
        curriculum = data.get("curriculum")
        if not isinstance(curriculum, str) or not _SUBJECT_RE.match(curriculum):
            raise CatalogValidationError(f"{source}: curriculum must be a lowercase slug")

        levels = data.get("levels", [])
        subjects = data.get("subjects", [])
        objectives = data.get("objectives", [])
        if not isinstance(levels, list) or len(levels) > _MAX_LEVELS:
            raise CatalogValidationError(f"{source}: levels must be a list (<= {_MAX_LEVELS})")
        if not isinstance(subjects, list) or len(subjects) > _MAX_SUBJECTS:
            raise CatalogValidationError(f"{source}: subjects must be a list (<= {_MAX_SUBJECTS})")
        if not isinstance(objectives, list) or not objectives \
                or len(objectives) > _MAX_OBJECTIVES:
            raise CatalogValidationError(
                f"{source}: objectives must be a non-empty list (<= {_MAX_OBJECTIVES})")

        for lv in levels:
            if not isinstance(lv, str) or not _LEVEL_RE.match(lv):
                raise CatalogValidationError(f"{source}: invalid level {lv!r}")
        for sub in subjects:
            if not isinstance(sub, str) or not _SUBJECT_RE.match(sub):
                raise CatalogValidationError(f"{source}: invalid subject {sub!r}")

        level_set = set(levels)
        subject_set = set(subjects)
        by_id = {}
        for obj in objectives:
            if not isinstance(obj, dict):
                raise CatalogValidationError(f"{source}: each objective must be an object")
            allowed = {"id", "level", "subject", "title", "expected_notions"}
            extra = set(obj) - allowed
            if extra:
                raise CatalogValidationError(
                    f"{source}: objective has unknown keys {sorted(extra)}")
            oid = obj.get("id")
            if not isinstance(oid, str) or not _OBJECTIVE_ID_RE.match(oid):
                raise CatalogValidationError(f"{source}: invalid objective id {oid!r}")
            if oid in by_id:
                raise CatalogValidationError(f"{source}: duplicate objective id {oid!r}")
            lvl = obj.get("level")
            if not isinstance(lvl, str) or not _LEVEL_RE.match(lvl):
                raise CatalogValidationError(f"{source}: objective {oid!r} invalid level")
            if level_set and lvl not in level_set:
                raise CatalogValidationError(
                    f"{source}: objective {oid!r} level {lvl!r} not in levels[]")
            sub = obj.get("subject")
            if not isinstance(sub, str) or not _SUBJECT_RE.match(sub):
                raise CatalogValidationError(f"{source}: objective {oid!r} invalid subject")
            if subject_set and sub not in subject_set:
                raise CatalogValidationError(
                    f"{source}: objective {oid!r} subject {sub!r} not in subjects[]")
            _safe_text(obj.get("title"), f"objective {oid!r} title")
            notions = obj.get("expected_notions", [])
            if not isinstance(notions, list) or len(notions) > _MAX_NOTIONS:
                raise CatalogValidationError(
                    f"{source}: objective {oid!r} expected_notions must be a list "
                    f"(<= {_MAX_NOTIONS})")
            for n in notions:
                _safe_text(n, f"objective {oid!r} expected_notions[]")
            by_id[oid] = obj

        self.catalog_version = cv
        self.curriculum = curriculum
        self.levels = tuple(levels)
        self.subjects = tuple(subjects)
        self._by_id = by_id

    def get_objective(self, objective_id):
        """Return the validated objective dict, or None if unknown."""
        return self._by_id.get(objective_id)

    def has_level(self, level):
        return level in self.levels

    def has_subject(self, subject):
        return subject in self.subjects


class FileCatalogProvider:
    """Reads catalogs from JSON files named `<catalog_id>.v<version>.json` under
    `catalogs_dir`. Validates at load (fail fast). No caching in v0 — catalogs
    are tiny and this keeps `/v1/chat` deterministic w.r.t. on-disk state.

    `catalog_id` is supplied by api.py from the AUTHENTICATED tenant's config,
    never from the request body → cross-tenant reads are impossible."""

    def __init__(self, catalogs_dir):
        self.catalogs_dir = catalogs_dir

    def get_catalog(self, catalog_id, version):
        # Defensive: reject anything that isn't a clean id/version BEFORE it
        # ever touches the filesystem (no path traversal via a crafted config).
        if not isinstance(catalog_id, str) or not _CATALOG_ID_RE.match(catalog_id):
            raise CatalogValidationError(f"invalid catalog id {catalog_id!r}")
        if not isinstance(version, str) or not _VERSION_RE.match(version):
            raise CatalogValidationError(f"invalid catalog version {version!r}")
        fname = f"{catalog_id}.v{version}.json"
        path = os.path.join(self.catalogs_dir, fname)
        # Confirm the resolved path stays inside catalogs_dir (belt-and-braces;
        # the regexes already forbid separators and dots-runs).
        base = os.path.abspath(self.catalogs_dir)
        full = os.path.abspath(path)
        if os.path.dirname(full) != base:
            raise CatalogValidationError(f"catalog path escapes catalogs dir: {fname}")
        if not os.path.isfile(full):
            raise CatalogNotFoundError(f"no catalog {catalog_id} v{version}")
        try:
            with open(full, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise CatalogValidationError(f"catalog {fname} unreadable: {type(e).__name__}")
        cat = Catalog(data, source=fname)
        # The catalog_version inside the file must match the requested version
        # (guards against a mislabeled/renamed file).
        if cat.catalog_version != version:
            raise CatalogValidationError(
                f"catalog {fname}: catalog_version {cat.catalog_version!r} "
                f"!= requested {version!r}")
        return cat
