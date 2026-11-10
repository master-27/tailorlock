import pytest
from pydantic import ValidationError

from tailorlock.schema import Patch, SectionPatch
from tailorlock.validate import errors_only, validate_patch

SDE = "exp-acme-sde"


def codes(issues):
    return sorted(i.code for i in errors_only(issues))


def test_good_patch_has_no_errors(master, policy, good_patch):
    assert errors_only(validate_patch(master, policy, good_patch)) == []


def test_unknown_ids_are_rejected(master, policy, good_patch):
    good_patch.skills = ["sk-java", "sk-nope"] + [s.id for s in master.skills][1:25]
    good_patch.sections[SDE].include = ["exp-acme-sde-pay", "nope"]
    good_patch.sections["exp-ghost"] = SectionPatch(include=[])
    c = codes(validate_patch(master, policy, good_patch))
    assert "unknown_skill" in c and "unknown_bullet" in c and "unknown_section" in c


def test_new_numbers_are_rejected(master, policy, good_patch):
    good_patch.sections[SDE].rewrites = {"exp-acme-sde-pay": "Integrated payments supporting **500 Cr+** monthly volume."}
    assert "new_number" in codes(validate_patch(master, policy, good_patch))


def test_existing_numbers_are_allowed(master, policy, good_patch):
    good_patch.sections[SDE].rewrites = {
        "exp-acme-sde-pay": "Integrated payment gateway workflows handling **120 Cr+ monthly payment volume** with reconciliation for credit/debit notes, deductions and buyer payments."
    }
    assert "new_number" not in codes(validate_patch(master, policy, good_patch))


def test_bold_markers_do_not_count_toward_length(master, policy, good_patch):
    base = "x" * (policy.editable.bullets.max_chars - 2)
    good_patch.sections[SDE].rewrites = {"exp-acme-sde-infra": "**" + base + "**"}
    assert "too_long" not in codes(validate_patch(master, policy, good_patch))
    good_patch.sections[SDE].rewrites = {"exp-acme-sde-infra": "**" + base}
    assert "unbalanced_bold" in codes(validate_patch(master, policy, good_patch))


def test_rewrite_must_be_included(master, policy, good_patch):
    good_patch.sections[SDE].rewrites = {"exp-acme-sde-prefetch": "Prefetching."}
    assert "rewrite_not_included" in codes(validate_patch(master, policy, good_patch))


def test_relabel_rules(master, policy, good_patch):
    good_patch.sections[SDE].relabel = {"exp-acme-sde-notif": "Event-Driven Processing"}
    assert errors_only(validate_patch(master, policy, good_patch)) == []
    good_patch.sections[SDE].relabel = {"exp-acme-sde-notif": "Event-Driven Processing:"}
    assert "label_colon" in codes(validate_patch(master, policy, good_patch))
    good_patch.sections[SDE].relabel = {}
    good_patch.sections["prj-mentor"].relabel = {"prj-mentor-rag": "RAG"}
    assert "label_not_allowed" in codes(validate_patch(master, policy, good_patch))


def test_title_is_disabled_for_this_layout(master, policy, good_patch):
    good_patch.title = "Backend Engineer"
    assert "title_disabled" in codes(validate_patch(master, policy, good_patch))


def test_owner_not_claimed_tools_are_forbidden(master, policy, good_patch):
    good_patch.summary = "Software engineer with experience in React, Next.js and Redux building production systems for payments and procurement across Node.js and Go, with AWS deployments and CI/CD pipelines in place."
    assert "forbidden_phrase" in codes(validate_patch(master, policy, good_patch))


def test_style_rules(master, policy, good_patch):
    good_patch.summary = "I am a passionate, results-driven engineer who is responsible for synergy across teams and loves it. " * 3
    good_patch.sections[SDE].rewrites = {"exp-acme-sde-pay": "Responsible for payments."}
    c = codes(validate_patch(master, policy, good_patch))
    assert {"first_person", "forbidden_phrase", "weak_starter"} <= set(c)


def test_counts(master, policy, good_patch):
    good_patch.sections[SDE].include = [f"exp-acme-sde-{k}" for k in ("pay", "lock", "onboard", "notif", "infra", "agents", "feperf")]
    good_patch.sections["prj-mentor"].include = ["prj-mentor-rag"]
    good_patch.skills = ["sk-java"]
    c = codes(validate_patch(master, policy, good_patch))
    assert {"too_many_bullets", "too_few_bullets", "too_few_skills"} <= set(c)


def test_untouched_role_is_a_warning_not_error(master, policy, good_patch):
    del good_patch.sections[SDE]
    issues = validate_patch(master, policy, good_patch)
    assert errors_only(issues) == []
    assert any(i.code == "untouched_role_too_long" for i in issues)


def test_patch_schema_forbids_locked_fields():
    with pytest.raises(ValidationError):
        Patch.model_validate({"basics": {"name": "Someone Else"}})
    with pytest.raises(ValidationError):
        Patch.model_validate({"sections": {"exp-acme-sde": {"include": [], "company": "Google"}}})
    with pytest.raises(ValidationError):
        Patch.model_validate({"sections": {"exp-acme-sde": {"include": [], "start": "2019"}}})
