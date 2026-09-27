"""
Validateur forensique exhaustif. Diagnostic only.

Collecte TOUTES les violations d'un transport déjà parsé sans le muter.
Ne remplace PAS le validateur fail-fast de production.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.semantic_transport_decoder import _validate_kind_payload
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v3.handles import (
    owner_handle_for_kind,
    parse_link_handle,
)
from app.source_analysis_local_v3.links import ALLOWED_TARGET_HANDLE_KINDS, LINK_CARDINALITY
from app.source_analysis_local_v3.schema import V3_RECORD_FIELDS, V3_ROOT_FIELDS
from app.source_analysis_local_v3.source_refs import (
    classify_src_token,
    is_canonical_src,
    src_existence,
)
from app.source_analysis_v3_a19_forensics.constants import (
    EXAMPLE_POLICY,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)

_LOCAL = frozenset(LOCAL_KINDS)
_DEFERRED = frozenset(DEFERRED_KINDS)
_SUBSTANTIVE = frozenset({"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY"})


def _violation(
    *,
    code: str,
    location: str,
    message: str,
    class_: str,
    category: str,
    root_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "code": code,
        "location": location,
        "message": message,
        "class": class_,
        "category": category,
        "root_id": root_id,
    }
    if extra:
        row.update(extra)
    return row


def collect_transport_violations(
    payload: Mapping[str, Any] | None,
    *,
    allowed: set[str] | None,
    owned: set[str] | None,
    example_policy: str = EXAMPLE_POLICY,
) -> dict[str, Any]:
    """
    Inventaire exhaustif. payload n'est pas muté.
    Distingue ROOT vs CASCADE.
    """
    violations: list[dict[str, Any]] = []
    if not isinstance(payload, Mapping):
        violations.append(
            _violation(
                code="payload_not_object",
                location="$",
                message=f"payload type {type(payload).__name__}",
                class_="ROOT",
                category="record_shape",
            )
        )
        return _summarize(violations, payload, example_policy)

    leaked = forbidden_editorial_fields(payload)
    if leaked:
        violations.append(
            _violation(
                code="editorial_leak_root",
                location="$",
                message=str(leaked),
                class_="ROOT",
                category="metadata_contract",
            )
        )
    extra_root = [name for name in payload if name not in V3_ROOT_FIELDS]
    if extra_root:
        violations.append(
            _violation(
                code="unknown_root_fields",
                location="$",
                message=str(extra_root),
                class_="ROOT",
                category="record_shape",
            )
        )
    for field in ("theme", "intent", "ic", "aud", "ac"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            violations.append(
                _violation(
                    code="empty_header",
                    location=field,
                    message=f"{field} vide",
                    class_="ROOT",
                    category="record_shape",
                )
            )

    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        violations.append(
            _violation(
                code="records_not_list",
                location="records",
                message="records : une liste est attendue",
                class_="ROOT",
                category="record_shape",
            )
        )
        return _summarize(violations, payload, example_policy)

    idea_handles: dict[str, int] = {}
    topic_handles: dict[str, int] = {}
    owner_errors: dict[str, str] = {}

    for index, item in enumerate(raw_records):
        context = f"records[{index}]"
        if not isinstance(item, Mapping):
            violations.append(
                _violation(
                    code="record_not_object",
                    location=context,
                    message="un objet est attendu",
                    class_="ROOT",
                    category="record_shape",
                )
            )
            continue
        leaked_rec = forbidden_editorial_fields(item)
        if leaked_rec:
            violations.append(
                _violation(
                    code="editorial_leak_record",
                    location=context,
                    message=str(leaked_rec),
                    class_="ROOT",
                    category="metadata_contract",
                )
            )
        unknown_fields = [name for name in item if name not in V3_RECORD_FIELDS]
        if unknown_fields:
            violations.append(
                _violation(
                    code="unknown_record_fields",
                    location=context,
                    message=str(unknown_fields),
                    class_="ROOT",
                    category="record_shape",
                )
            )
        kind = item.get("k")
        if not isinstance(kind, str) or not kind.strip():
            violations.append(
                _violation(
                    code="kind_missing",
                    location=f"{context}.k",
                    message="k absent ou vide",
                    class_="ROOT",
                    category="kind",
                )
            )
            continue
        kind = kind.strip()
        if kind in _DEFERRED:
            violations.append(
                _violation(
                    code="deferred_kind",
                    location=f"{context}.k",
                    message=f"kind différé interdit « {kind} »",
                    class_="ROOT",
                    category="kind",
                )
            )
        elif kind not in _LOCAL:
            violations.append(
                _violation(
                    code="unknown_kind",
                    location=f"{context}.k",
                    message=f"kind inconnu « {kind} »",
                    class_="ROOT",
                    category="kind",
                )
            )

        value = item.get("v")
        if not isinstance(value, str):
            violations.append(
                _violation(
                    code="value_not_string",
                    location=f"{context}.v",
                    message="v doit être une chaîne",
                    class_="ROOT",
                    category="record_shape",
                )
            )
            value = ""

        raw_s = item.get("s")
        seen_src: set[str] = set()
        if raw_s is None:
            raw_s = []
        if not isinstance(raw_s, list):
            violations.append(
                _violation(
                    code="s_not_list",
                    location=f"{context}.s",
                    message="s : une liste de chaînes est attendue",
                    class_="ROOT",
                    category="source_refs",
                )
            )
            raw_s = []
        valid_src: list[str] = []
        for pos, token in enumerate(raw_s):
            loc = f"{context}.s[{pos}]"
            token_class = classify_src_token(token)
            if token_class != "canonical":
                code = {
                    "wrong_case": "src_wrong_case",
                    "whitespace_mutated": "src_whitespace",
                    "missing_zeros": "src_missing_zeros",
                    "excessive_digits": "src_excessive_digits",
                    "separator_mutated": "src_separator",
                    "non_digit_suffix": "src_non_digit_suffix",
                    "not_string": "src_not_string",
                }.get(token_class, "src_malformed")
                violations.append(
                    _violation(
                        code=code,
                        location=loc,
                        message=f"source_ref mal formé « {token} »",
                        class_="ROOT",
                        category="source_refs",
                        extra={"token": token if isinstance(token, str) else None,
                               "token_class": token_class},
                    )
                )
                continue
            assert isinstance(token, str)
            existence = src_existence(token, allowed=allowed, owned=owned)
            if existence == "unknown":
                in_owned_universe = owned is not None and token in owned
                code = "src_unknown" if not in_owned_universe else "src_out_of_window"
                if allowed is not None and token not in allowed:
                    code = (
                        "src_out_of_window"
                        if owned is not None and token not in owned
                        else "src_unknown"
                    )
                violations.append(
                    _violation(
                        code=code,
                        location=loc,
                        message=f"source_ref inconnu/hors fenêtre « {token} »",
                        class_="ROOT",
                        category="source_refs",
                        extra={"token": token, "existence": existence},
                    )
                )
                continue
            if token in seen_src:
                violations.append(
                    _violation(
                        code="src_duplicate",
                        location=loc,
                        message=f"source_ref dupliqué « {token} »",
                        class_="ROOT",
                        category="source_refs",
                        extra={"token": token},
                    )
                )
                continue
            seen_src.add(token)
            valid_src.append(token)
        if kind in _SUBSTANTIVE and not valid_src and not any(
            row["location"].startswith(f"{context}.s") for row in violations
        ):
            violations.append(
                _violation(
                    code="src_empty_required",
                    location=f"{context}.s",
                    message=f"{kind} exige s[] non vide",
                    class_="ROOT",
                    category="source_refs",
                )
            )
        if kind == "RELATION" and valid_src:
            violations.append(
                _violation(
                    code="src_forbidden_for_relation",
                    location=f"{context}.s",
                    message="RELATION exige s=[]",
                    class_="ROOT",
                    category="source_refs",
                )
            )

        handle, handle_err = owner_handle_for_kind(kind, item.get("h"))
        if handle_err:
            root_id = f"owner:{context}"
            violations.append(
                _violation(
                    code="owner_handle_invalid",
                    location=f"{context}.h",
                    message=handle_err,
                    class_="ROOT",
                    category="owner_handles",
                    root_id=root_id,
                    extra={"raw": item.get("h")},
                )
            )
            owner_errors[str(item.get("h"))] = root_id
        elif kind == "TOPIC" and handle:
            if handle in topic_handles:
                violations.append(
                    _violation(
                        code="duplicate_owner",
                        location=f"{context}.h",
                        message=f"handle owner dupliqué « {handle} »",
                        class_="ROOT",
                        category="handle_uniqueness",
                        root_id=f"dup-owner:{handle}",
                    )
                )
            topic_handles.setdefault(handle, index)
        elif kind == "IDEA" and handle:
            if handle in idea_handles:
                violations.append(
                    _violation(
                        code="duplicate_owner",
                        location=f"{context}.h",
                        message=f"handle owner dupliqué « {handle} »",
                        class_="ROOT",
                        category="handle_uniqueness",
                        root_id=f"dup-owner:{handle}",
                    )
                )
            idea_handles.setdefault(handle, index)

        raw_links = item.get("l")
        if raw_links is None:
            raw_links = []
        if not isinstance(raw_links, list):
            violations.append(
                _violation(
                    code="l_not_list",
                    location=f"{context}.l",
                    message="l : une liste de handles est attendue",
                    class_="ROOT",
                    category="link_handles",
                )
            )
            raw_links = []
        parsed_links: list[str] = []
        seen_links: set[str] = set()
        for pos, raw in enumerate(raw_links):
            loc = f"{context}.l[{pos}]"
            if isinstance(raw, bool) or isinstance(raw, int):
                violations.append(
                    _violation(
                        code="numeric_link_regression",
                        location=loc,
                        message=f"handle lien numérique interdit « {raw} »",
                        class_="ROOT",
                        category="link_handles",
                        extra={"raw": raw},
                    )
                )
                continue
            parsed, err = parse_link_handle(raw)
            if err:
                violations.append(
                    _violation(
                        code="malformed_link_handle",
                        location=loc,
                        message=err,
                        class_="ROOT",
                        category="link_handles",
                        extra={"raw": raw},
                    )
                )
                continue
            assert parsed is not None
            if parsed in seen_links:
                violations.append(
                    _violation(
                        code="duplicate_target",
                        location=context,
                        message=f"handle cible dupliqué {parsed}",
                        class_="ROOT",
                        category="duplicate_targets",
                    )
                )
            seen_links.add(parsed)
            parsed_links.append(parsed)

        meta_errors: list[str] = []
        _validate_kind_payload(
            kind=kind,
            value=str(value or "").strip(),
            source_refs=valid_src,
            links=list(range(len(parsed_links))),
            metadata=[
                str(slot).strip()
                for slot in (item.get("m") or [])
                if isinstance(slot, str)
            ]
            if isinstance(item.get("m"), list)
            else [],
            context=context,
            errors=meta_errors,
        )
        if not isinstance(item.get("m"), list) and item.get("m") is not None:
            violations.append(
                _violation(
                    code="m_not_list",
                    location=f"{context}.m",
                    message="m : une liste de chaînes est attendue",
                    class_="ROOT",
                    category="metadata_contract",
                )
            )
        for err in meta_errors:
            if "s (source_refs) requis" in err or "s doit être vide" in err:
                continue
            violations.append(
                _violation(
                    code="metadata_or_kind_payload",
                    location=context,
                    message=err,
                    class_="ROOT",
                    category="metadata_contract",
                )
            )

    idea_exists = bool(idea_handles)
    for index, item in enumerate(raw_records):
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("k") or "")
        context = f"records[{index}]"
        raw_links = item.get("l") if isinstance(item.get("l"), list) else []
        parsed_links: list[str] = []
        for raw in raw_links:
            parsed, err = parse_link_handle(raw)
            if err or parsed is None:
                continue
            target_kind = "TOPIC" if parsed.startswith("T") else (
                "IDEA" if parsed.startswith("I") else None
            )
            allowed_targets = ALLOWED_TARGET_HANDLE_KINDS.get(kind)
            if allowed_targets is not None and target_kind not in allowed_targets:
                violations.append(
                    _violation(
                        code="wrong_kind_handle",
                        location=context,
                        message=(
                            f"{kind} ne peut cibler que "
                            f"{sorted(allowed_targets) or 'aucun'} handle, "
                            f"pas {target_kind} ({parsed})"
                        ),
                        class_="ROOT",
                        category="wrong_kind_handles",
                        extra={"handle": parsed},
                    )
                )
                continue
            registry = idea_handles if target_kind == "IDEA" else topic_handles
            if parsed not in registry:
                owner_root = owner_errors.get(parsed)
                violations.append(
                    _violation(
                        code="unknown_handle",
                        location=context,
                        message=f"handle inconnu « {parsed} »",
                        class_="CASCADE" if owner_root else "ROOT",
                        category="unknown_handles",
                        root_id=owner_root,
                        extra={"handle": parsed},
                    )
                )
                continue
            parsed_links.append(parsed)
        card = LINK_CARDINALITY.get(kind)
        if card is not None:
            if card["empty"] == "required" and parsed_links:
                violations.append(
                    _violation(
                        code="l_must_be_empty",
                        location=f"{context}.l",
                        message=f"{kind} exige l=[]",
                        class_="ROOT",
                        category="per_kind_cardinality",
                    )
                )
            if card["empty"] == "forbidden" and not parsed_links:
                violations.append(
                    _violation(
                        code="l_required",
                        location=f"{context}.l",
                        message=f"{kind} exige des handles",
                        class_="ROOT",
                        category="per_kind_cardinality",
                    )
                )
            if kind == "EXAMPLE" and not parsed_links and idea_exists:
                if example_policy == "A_REQUIRE_IDEA_IF_ANY_EXISTS":
                    violations.append(
                        _violation(
                            code="example_empty_link_current_v3",
                            location=f"{context}.l",
                            message="EXAMPLE.l vide interdit tant qu'une IDEA locale existe",
                            class_="ROOT",
                            category="per_kind_cardinality",
                        )
                    )
                else:
                    violations.append(
                        _violation(
                            code="example_empty_link_a19_era_rule_only",
                            location=f"{context}.l",
                            message=(
                                "A.19-era V3 rule would reject empty EXAMPLE.l "
                                "because local IDEAs exist. Settled canonical "
                                f"policy {example_policy} does not treat this as "
                                "a transport-validity root violation."
                            ),
                            class_="OBSERVATION",
                            category="per_kind_cardinality",
                            extra={"settled_policy": example_policy},
                        )
                    )
            maximum = card["max"]
            if maximum is not None and maximum > 0 and len(parsed_links) > maximum:
                violations.append(
                    _violation(
                        code="l_overflow",
                        location=f"{context}.l",
                        message=f"{kind} accepte au plus {maximum} handle(s)",
                        class_="ROOT",
                        category="per_kind_cardinality",
                    )
                )
        if kind == "RELATION" and len(parsed_links) == 2 and parsed_links[0] == parsed_links[1]:
            violations.append(
                _violation(
                    code="self_relation",
                    location=context,
                    message=f"RELATION auto-cible interdite {parsed_links}",
                    class_="ROOT",
                    category="self_relations",
                )
            )

    return _summarize(violations, payload, example_policy)


def _summarize(
    violations: list[dict[str, Any]],
    payload: Mapping[str, Any] | None,
    example_policy: str,
) -> dict[str, Any]:
    roots = [row for row in violations if row["class"] == "ROOT"]
    cascades = [row for row in violations if row["class"] == "CASCADE"]
    observations = [row for row in violations if row["class"] == "OBSERVATION"]
    by_code: dict[str, int] = {}
    for row in violations:
        by_code[row["code"]] = by_code.get(row["code"], 0) + 1
    records = []
    if isinstance(payload, Mapping) and isinstance(payload.get("records"), list):
        records = [item for item in payload["records"] if isinstance(item, Mapping)]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "diagnostic_only": True,
        "mutated_transport": False,
        "replaces_production_fail_fast": False,
        "example_policy_applied": example_policy,
        "record_count": len(records),
        "violations": violations,
        "root_violations": roots,
        "cascade_violations": cascades,
        "observations": observations,
        "total_latent_root_violations": len(roots),
        "total_cascade_violations": len(cascades),
        "total_observations": len(observations),
        "by_code": by_code,
        "counts": {
            "malformed_src": by_code.get("src_malformed", 0)
            + by_code.get("src_wrong_case", 0)
            + by_code.get("src_whitespace", 0)
            + by_code.get("src_missing_zeros", 0)
            + by_code.get("src_excessive_digits", 0)
            + by_code.get("src_separator", 0)
            + by_code.get("src_non_digit_suffix", 0)
            + by_code.get("src_not_string", 0),
            "wrong_case_src": by_code.get("src_wrong_case", 0),
            "unknown_src": by_code.get("src_unknown", 0),
            "out_of_window_src": by_code.get("src_out_of_window", 0),
            "duplicate_src": by_code.get("src_duplicate", 0),
            "handle_root": sum(
                1
                for row in roots
                if row["category"]
                in {
                    "owner_handles",
                    "link_handles",
                    "handle_uniqueness",
                    "unknown_handles",
                    "wrong_kind_handles",
                    "duplicate_targets",
                    "self_relations",
                    "per_kind_cardinality",
                }
            ),
            "unknown_handles": by_code.get("unknown_handle", 0),
            "wrong_kind_handles": by_code.get("wrong_kind_handle", 0),
            "duplicate_owners": by_code.get("duplicate_owner", 0),
            "self_relations": by_code.get("self_relation", 0),
            "numeric_link_regression": by_code.get("numeric_link_regression", 0),
            "example_empty_link_settled": by_code.get(
                "example_empty_link_current_v3", 0
            ),
            "example_empty_link_a19_era_observations": by_code.get(
                "example_empty_link_a19_era_rule_only", 0
            ),
        },
    }


__all__ = ["collect_transport_violations"]
