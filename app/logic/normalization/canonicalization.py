"""Bundle-local canonicalization helpers for parser/AST drift hardening."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import Sequence

from app.logic.ast.nodes import (
    AndNode,
    ArithNode,
    CompareNode,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    LogicNode,
    NotNode,
    NumRefNode,
    OrNode,
    PredNode,
)
from app.logic.ast.terms import ConstTerm, NumberTerm, Term, VarTerm

from .logic import normalize_logic_ast

_LIGHT_TOKENS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "to",
        "of",
        "for",
        "with",
        "that",
        "this",
        "those",
        "these",
        "who",
        "which",
        "has",
        "have",
        "had",
    }
)
_MODAL_STEMS = frozenset(
    {
        "need",
        "requir",
        "must",
        "qualifi",
        "eligible",
        "award",
        "complet",
        "pass",
        "receiv",
    }
)
_RELATION_VERBS = frozenset(
    {
        "has",
        "have",
        "had",
        "completed",
        "passed",
        "received",
        "awarded",
        "needs",
        "need",
        "requires",
        "require",
        "eligible",
        "qualify",
        "qualified",
        "qualifies",
    }
)
_RELATION_VERB_HINTS: dict[str, str] = {
    "complete": "completed",
    "completed": "completed",
    "pass": "passed",
    "passed": "passed",
    "receive": "received",
    "received": "received",
    "award": "awarded",
    "awarded": "awarded",
    "need": "needs",
    "needs": "needs",
    "require": "requires",
    "requires": "requires",
    "eligible": "eligible",
    "qualify": "qualify",
    "qualified": "qualify",
    "qualifies": "qualify",
    "has": "has",
    "have": "has",
    "had": "has",
}
_POSSESSIVE_TOKENS = frozenset({"my", "our", "your", "his", "her", "their", "its"})
_ENTITY_PREFIX_TOKENS = frozenset({"a", "an", "the", *_POSSESSIVE_TOKENS})
_ENTITY_DESCRIPTOR_TOKENS = frozenset({"required", "mandatory", "optional"})
_ENTITY_SUFFIX_TOKENS = frozenset({"course", "courses", "hour", "hours"})
_MAX_WARNING_DETAILS = 12


@dataclass(frozen=True)
class CanonicalizationResult:
    premise_asts: list[LogicNode]
    candidate_asts: list[LogicNode]
    warnings: list[str]
    predicate_alias_count: int
    predicate_alias_rejected_count: int
    entity_alias_count: int
    entity_alias_rejected_count: int
    relation_repair_count: int
    relation_repair_rejected_count: int


def canonicalize_logic_bundle(
    premise_asts: Sequence[LogicNode],
    candidate_asts: Sequence[LogicNode],
) -> CanonicalizationResult:
    normalized_premises = [normalize_logic_ast(item) for item in premise_asts]
    normalized_candidates = [normalize_logic_ast(item) for item in candidate_asts]

    (
        repaired_premises,
        repaired_candidates,
        relation_warnings,
        relation_repairs,
        relation_rejected,
    ) = _repair_relation_arguments(normalized_premises, normalized_candidates)

    predicate_aliases, predicate_rejected, predicate_warnings = _build_predicate_aliases(
        [*repaired_premises, *repaired_candidates]
    )
    entity_aliases, entity_rejected = _build_entity_aliases([*repaired_premises, *repaired_candidates])

    canonicalized_premises = [_rewrite_node(item, predicate_aliases, entity_aliases) for item in repaired_premises]
    canonicalized_candidates = [_rewrite_node(item, predicate_aliases, entity_aliases) for item in repaired_candidates]

    predicate_alias_count = sum(1 for key, value in predicate_aliases.items() if key[1] != value)
    entity_alias_count = sum(1 for key, value in entity_aliases.items() if key != value)

    warnings = [*relation_warnings, *predicate_warnings]
    if predicate_alias_count:
        warnings.append(f"predicate_aliases_applied:{predicate_alias_count}")
    if predicate_rejected:
        warnings.append(f"predicate_aliases_rejected:{predicate_rejected}")
    if entity_alias_count:
        warnings.append(f"entity_aliases_applied:{entity_alias_count}")
    if entity_rejected:
        warnings.append(f"entity_aliases_rejected:{entity_rejected}")
    if relation_rejected:
        warnings.append(f"relation_argument_repairs_rejected:{relation_rejected}")

    return CanonicalizationResult(
        premise_asts=canonicalized_premises,
        candidate_asts=canonicalized_candidates,
        warnings=warnings,
        predicate_alias_count=predicate_alias_count,
        predicate_alias_rejected_count=predicate_rejected,
        entity_alias_count=entity_alias_count,
        entity_alias_rejected_count=entity_rejected,
        relation_repair_count=relation_repairs,
        relation_repair_rejected_count=relation_rejected,
    )


def _repair_relation_arguments(
    premise_asts: Sequence[LogicNode],
    candidate_asts: Sequence[LogicNode],
) -> tuple[list[LogicNode], list[LogicNode], list[str], int, int]:
    warnings: list[str] = []
    accepted = 0
    rejected = 0

    def rewrite(node: LogicNode) -> LogicNode:
        nonlocal accepted, rejected
        if isinstance(node, PredNode):
            repaired, warning = _repair_relation_predicate(node)
            if repaired is not None:
                accepted += 1
                warnings.append(warning)
                return repaired
            if warning:
                rejected += 1
                if len(warnings) < _MAX_WARNING_DETAILS:
                    warnings.append(warning)
            return node
        if isinstance(node, NotNode):
            return replace(node, body=rewrite(node.body))
        if isinstance(node, AndNode):
            return replace(node, operands=[rewrite(item) for item in node.operands])
        if isinstance(node, OrNode):
            return replace(node, operands=[rewrite(item) for item in node.operands])
        if isinstance(node, ImpliesNode):
            return replace(node, if_node=rewrite(node.if_node), then=rewrite(node.then))
        if isinstance(node, ForallNode | ExistsNode):
            return replace(node, body=rewrite(node.body))
        if isinstance(node, CompareNode):
            return replace(node, left=_rewrite_numeric_expr(node.left, rewrite), right=_rewrite_numeric_expr(node.right, rewrite))
        if isinstance(node, ArithNode):
            return replace(node, operands=[_rewrite_numeric_expr(item, rewrite) for item in node.operands])
        if isinstance(node, NumRefNode):
            return replace(node, args=[_rewrite_term(item, {}) for item in node.args])
        return node

    return [rewrite(item) for item in premise_asts], [rewrite(item) for item in candidate_asts], warnings, accepted, rejected


def _repair_relation_predicate(node: PredNode) -> tuple[PredNode | None, str | None]:
    if len(node.args) != 1:
        return None, None
    first_arg = node.args[0]
    if not isinstance(first_arg, ConstTerm | VarTerm):
        return None, None

    source_text = " ".join((node.source_text or "").split()).strip()
    if not source_text:
        return None, None

    verb = _infer_relation_verb_for_predicate(node.name, source_text)
    if verb is None:
        return None, None
    object_phrase = _extract_object_phrase(source_text, verb)
    if object_phrase is None:
        return None, f"relation_arguments_rejected:no_object:{node.source_id or 'unknown'}:{node.name}"

    object_const = ConstTerm(kind="const", name=object_phrase, surface=object_phrase.replace("_", " "))
    subject_phrase = _extract_subject_phrase(source_text)
    subject_const = (
        ConstTerm(kind="const", name=subject_phrase, surface=subject_phrase.replace("_", " "))
        if subject_phrase is not None
        else None
    )

    if isinstance(first_arg, ConstTerm):
        first_signature = _entity_signature(first_arg.name)
        object_signature = _entity_signature(object_phrase)
        subject_signature = _entity_signature(subject_phrase) if subject_phrase is not None else None

        if first_signature == object_signature and subject_const is not None:
            updated_name = _relation_name(node.name, verb, object_phrase)
            return (
                replace(node, name=updated_name, args=[subject_const, first_arg]),
                f"relation_arguments_recovered:object_subject:{node.source_id or 'unknown'}:{node.name}",
            )
        if subject_signature is not None and first_signature == subject_signature:
            updated_name = _relation_name(node.name, verb, object_phrase)
            return (
                replace(node, name=updated_name, args=[first_arg, object_const]),
                f"relation_arguments_recovered:subject_object:{node.source_id or 'unknown'}:{node.name}",
            )
        return None, f"relation_arguments_rejected:subject_object_mismatch:{node.source_id or 'unknown'}:{node.name}"

    # first_arg is a bound variable
    updated_name = _relation_name(node.name, verb, object_phrase)
    return (
        replace(node, name=updated_name, args=[first_arg, object_const]),
        f"relation_arguments_recovered:variable_object:{node.source_id or 'unknown'}:{node.name}",
    )


def _relation_name(original_name: str, verb: str, object_phrase: str) -> str:
    if verb in {"completed", "complete"} or "completed" in object_phrase:
        if original_name in {"has", "have", "had"}:
            return "has_completed"
        return "completed"
    if verb in {"passed", "pass"} or "passed" in object_phrase:
        if original_name in {"has", "have", "had"}:
            return "has_passed"
        return "passed"
    if verb in {"received", "receive"} or "received" in object_phrase:
        if original_name in {"has", "have", "had"}:
            return "has_received"
        return "received"
    if verb in {"awarded", "award"} or "awarded" in object_phrase:
        if original_name in {"has", "have", "had"}:
            return "has_awarded"
        return "awarded"
    if verb in {"needs", "need"}:
        return "needs"
    if verb in {"requires", "require"}:
        return "requires"
    if verb in {"eligible"}:
        return "eligible_for"
    if verb in {"qualify", "qualified", "qualifies"}:
        return "qualifies_for"
    return original_name


def _infer_relation_verb_for_predicate(predicate_name: str, source_text: str) -> str | None:
    for token in predicate_name.split("_"):
        lowered = token.strip().lower()
        hinted = _RELATION_VERB_HINTS.get(lowered)
        if hinted is not None:
            if hinted == "has":
                return _extract_relation_verb(source_text)
            return hinted
    return _extract_relation_verb(source_text)


def _extract_relation_verb(source_text: str) -> str | None:
    with_index = _extract_relation_verb_with_index(source_text)
    if with_index is None:
        return None
    return with_index[0]


def _extract_relation_verb_with_index(source_text: str) -> tuple[str, int] | None:
    words = _tokenize_words(source_text)
    for index, word in enumerate(words):
        if word in {"has", "have", "had"} and index + 1 < len(words):
            next_word = words[index + 1]
            if next_word in _RELATION_VERBS and next_word not in {"has", "have", "had"}:
                return next_word, index + 1
        if word in _RELATION_VERBS:
            return word, index
    return None


def _extract_subject_phrase(source_text: str) -> str | None:
    words = _tokenize_words(source_text)
    if not words:
        return None
    relation = _extract_relation_verb_with_index(source_text)
    limit = relation[1] if relation is not None else len(words)
    subject_tokens = [token for token in words[:limit] if token and token not in _ENTITY_PREFIX_TOKENS and token not in _LIGHT_TOKENS]
    if not subject_tokens:
        return None
    return _to_snake_case(subject_tokens[0])


def _extract_object_phrase(source_text: str, verb: str) -> str | None:
    words = _tokenize_words(source_text)
    verb_index = -1
    for index, word in enumerate(words):
        if word == verb:
            verb_index = index
            break
    if verb_index < 0:
        relation = _extract_relation_verb_with_index(source_text)
        if relation is None:
            return None
        _, verb_index = relation

    object_tokens: list[str] = []
    for token in words[verb_index + 1 :]:
        if token in {"then", "are", "is", "and", "who", "that"}:
            break
        if token == "to" and object_tokens:
            break
        object_tokens.append(token)

    while object_tokens and object_tokens[0] in {"to", "for", *_ENTITY_PREFIX_TOKENS}:
        object_tokens = object_tokens[1:]
    if not object_tokens:
        return None

    snake = _normalize_relation_object_phrase(_to_snake_case(" ".join(object_tokens)))
    if not snake or snake in {"it", "they", "them", "student", "students"}:
        return None
    return snake


def _build_predicate_aliases(nodes: Sequence[LogicNode]) -> tuple[dict[tuple[int, str], str], int, list[str]]:
    grouped: dict[tuple[int, tuple[str, ...]], set[str]] = {}
    legacy_grouped: dict[tuple[int, str], set[str]] = {}
    for node in nodes:
        for pred in _iter_predicates(node):
            strict_key = (len(pred.args), tuple(_semantic_tokens(pred.name)))
            grouped.setdefault(strict_key, set()).add(pred.name)
            legacy_grouped.setdefault((len(pred.args), _legacy_predicate_signature(pred.name)), set()).add(pred.name)

    aliases: dict[tuple[int, str], str] = {}
    rejected = 0
    warnings: list[str] = []

    for (arity, semantic_key), names in grouped.items():
        names_sorted = sorted(names)
        if len(names_sorted) == 1:
            aliases[(arity, names_sorted[0])] = names_sorted[0]
            continue
        if not _is_safe_predicate_alias_group(names_sorted):
            rejected += len(names_sorted)
            for name in names_sorted:
                aliases[(arity, name)] = name
            if len(warnings) < _MAX_WARNING_DETAILS:
                warnings.append(f"predicate_alias_rejected:unsafe_group:{','.join(names_sorted)}")
            continue
        canonical = max(names_sorted, key=lambda item: (len(item.split("_")), len(item), item))
        for name in names_sorted:
            aliases[(arity, name)] = canonical

    # Additional rejection diagnostics for legacy over-broad groups.
    for (arity, _), names in legacy_grouped.items():
        if len(names) < 2:
            continue
        for left, right in combinations(sorted(names), 2):
            left_alias = aliases.get((arity, left), left)
            right_alias = aliases.get((arity, right), right)
            if left_alias != right_alias:
                rejected += 1
                if len(warnings) < _MAX_WARNING_DETAILS:
                    warnings.append(f"predicate_alias_rejected:legacy_pair:{left}!={right}")

    return aliases, rejected, warnings


def _is_safe_predicate_alias_group(names: Sequence[str]) -> bool:
    profiles = {_modal_profile(name) for name in names}
    if len(profiles) != 1:
        return False
    semantic_heads = {_semantic_head(name) for name in names}
    if len(semantic_heads) != 1:
        return False
    semantic_keys = {tuple(_semantic_tokens(name)) for name in names}
    return len(semantic_keys) == 1


def _build_entity_aliases(nodes: Sequence[LogicNode]) -> tuple[dict[str, str], int]:
    grouped: dict[tuple[str, ...], set[str]] = {}
    for node in nodes:
        for const_name in _iter_const_names(node):
            grouped.setdefault(tuple(_entity_tokens(const_name)), set()).add(const_name)

    aliases: dict[str, str] = {}
    rejected = 0
    for key, names in grouped.items():
        names_sorted = sorted(names)
        if len(names_sorted) == 1:
            aliases[names_sorted[0]] = names_sorted[0]
            continue
        if not key:
            rejected += len(names_sorted)
            for name in names_sorted:
                aliases[name] = name
            continue
        canonical = max(names_sorted, key=lambda item: (len(item.split("_")), len(item), item))
        for name in names_sorted:
            aliases[name] = canonical
    return aliases, rejected


def _rewrite_node(
    node: LogicNode,
    predicate_aliases: dict[tuple[int, str], str],
    entity_aliases: dict[str, str],
) -> LogicNode:
    if isinstance(node, PredNode):
        name = predicate_aliases.get((len(node.args), node.name), node.name)
        args = [_rewrite_term(item, entity_aliases) for item in node.args]
        return replace(node, name=name, args=args)
    if isinstance(node, NotNode):
        return replace(node, body=_rewrite_node(node.body, predicate_aliases, entity_aliases))
    if isinstance(node, AndNode):
        return replace(node, operands=[_rewrite_node(item, predicate_aliases, entity_aliases) for item in node.operands])
    if isinstance(node, OrNode):
        return replace(node, operands=[_rewrite_node(item, predicate_aliases, entity_aliases) for item in node.operands])
    if isinstance(node, ImpliesNode):
        return replace(
            node,
            if_node=_rewrite_node(node.if_node, predicate_aliases, entity_aliases),
            then=_rewrite_node(node.then, predicate_aliases, entity_aliases),
        )
    if isinstance(node, ForallNode | ExistsNode):
        return replace(node, body=_rewrite_node(node.body, predicate_aliases, entity_aliases))
    if isinstance(node, CompareNode):
        return replace(
            node,
            left=_rewrite_numeric_expr(node.left, lambda item: _rewrite_node(item, predicate_aliases, entity_aliases)),
            right=_rewrite_numeric_expr(node.right, lambda item: _rewrite_node(item, predicate_aliases, entity_aliases)),
        )
    if isinstance(node, ArithNode):
        return replace(
            node,
            operands=[_rewrite_numeric_expr(item, lambda inner: _rewrite_node(inner, predicate_aliases, entity_aliases)) for item in node.operands],
        )
    if isinstance(node, NumRefNode):
        return replace(node, args=[_rewrite_term(item, entity_aliases) for item in node.args])
    return node


def _rewrite_numeric_expr(expression, node_rewriter):
    if isinstance(expression, NumberTerm | VarTerm):
        return expression
    if isinstance(expression, ConstTerm):
        return expression
    if isinstance(expression, NumRefNode | ArithNode):
        return node_rewriter(expression)
    return expression


def _rewrite_term(term: Term, entity_aliases: dict[str, str]) -> Term:
    if isinstance(term, ConstTerm):
        return replace(term, name=entity_aliases.get(term.name, term.name))
    return term


def _iter_predicates(node: LogicNode):
    if isinstance(node, PredNode):
        yield node
        return
    if isinstance(node, NotNode):
        yield from _iter_predicates(node.body)
        return
    if isinstance(node, AndNode | OrNode):
        for operand in node.operands:
            yield from _iter_predicates(operand)
        return
    if isinstance(node, ImpliesNode):
        yield from _iter_predicates(node.if_node)
        yield from _iter_predicates(node.then)
        return
    if isinstance(node, ForallNode | ExistsNode):
        yield from _iter_predicates(node.body)
        return


def _iter_const_names(node: LogicNode):
    for pred in _iter_predicates(node):
        for argument in pred.args:
            if isinstance(argument, ConstTerm):
                yield argument.name
    if isinstance(node, CompareNode):
        yield from _iter_const_names_in_numeric(node.left)
        yield from _iter_const_names_in_numeric(node.right)
    if isinstance(node, ArithNode):
        for operand in node.operands:
            yield from _iter_const_names_in_numeric(operand)
    if isinstance(node, NumRefNode):
        for argument in node.args:
            if isinstance(argument, ConstTerm):
                yield argument.name


def _iter_const_names_in_numeric(expression):
    if isinstance(expression, ConstTerm):
        yield expression.name
        return
    if isinstance(expression, NumRefNode):
        for argument in expression.args:
            if isinstance(argument, ConstTerm):
                yield argument.name
        return
    if isinstance(expression, ArithNode):
        for operand in expression.operands:
            yield from _iter_const_names_in_numeric(operand)


def _semantic_tokens(name: str) -> list[str]:
    tokens = []
    for raw in name.split("_"):
        token = raw.strip().lower()
        if not token or token in _LIGHT_TOKENS:
            continue
        tokens.append(_stem_token(token))
    return tokens


def _entity_tokens(name: str) -> list[str]:
    return _entity_core_tokens(name)


def _modal_profile(name: str) -> tuple[str, ...]:
    semantic = _semantic_tokens(name)
    return tuple(sorted(token for token in semantic if token in _MODAL_STEMS))


def _semantic_head(name: str) -> str:
    semantic = _semantic_tokens(name)
    return semantic[0] if semantic else name


def _legacy_predicate_signature(name: str) -> str:
    tokens = [_stem_token(token) for token in name.split("_") if token and token not in _LIGHT_TOKENS]
    return "_".join(tokens) or name


def _entity_signature(name: str | None) -> str:
    if not name:
        return ""
    return "_".join(_entity_tokens(name))


def _to_snake_case(text: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "_" for char in text)
    return "_".join(part for part in lowered.split("_") if part)


def _tokenize_words(text: str) -> list[str]:
    return [item.strip(" ,.:;!?").lower() for item in text.split() if item.strip(" ,.:;!?")]


def _normalize_relation_object_phrase(phrase: str) -> str:
    tokens = [token for token in phrase.split("_") if token]
    while tokens and tokens[0] in _ENTITY_PREFIX_TOKENS:
        tokens = tokens[1:]
    while len(tokens) > 2 and tokens[0] in _ENTITY_DESCRIPTOR_TOKENS:
        tokens = tokens[1:]
    while len(tokens) > 2 and tokens[-1] in _ENTITY_SUFFIX_TOKENS:
        tokens = tokens[:-1]
    return "_".join(tokens)


def _entity_core_tokens(name: str) -> list[str]:
    tokens = [token for token in name.split("_") if token]
    while tokens and tokens[0] in _ENTITY_PREFIX_TOKENS:
        tokens = tokens[1:]
    while len(tokens) > 2 and tokens[0] in _ENTITY_DESCRIPTOR_TOKENS:
        tokens = tokens[1:]
    while len(tokens) > 2 and tokens[-1] in _ENTITY_SUFFIX_TOKENS:
        tokens = tokens[:-1]
    return [_singularize_token(token) for token in tokens if token]


def _stem_token(token: str) -> str:
    singular = _singularize_token(token)
    if singular.endswith("ing") and len(singular) > 4:
        singular = singular[:-3]
    elif singular.endswith("ed") and len(singular) > 3:
        singular = singular[:-2]
    if singular.endswith("y") and len(singular) > 3:
        return singular[:-1] + "i"
    return singular


def _singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith(("sses", "shes", "ches", "xes", "zes")):
        return token[:-2]
    if len(token) > 2 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
