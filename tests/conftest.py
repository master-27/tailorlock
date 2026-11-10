import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tailorlock.schema import load_policy, load_resume  # noqa: E402


@pytest.fixture(scope="session")
def master():
    return load_resume(ROOT / "data" / "master.example.yaml")


@pytest.fixture(scope="session")
def policy():
    return load_policy(ROOT / "data" / "policy.yaml")


@pytest.fixture
def good_patch(master):
    from tailorlock.schema import Patch, SectionPatch

    return Patch(
        skills=[s.id for s in master.skills][:30],
        sections={
            "exp-acme-sde": SectionPatch(include=[
                "exp-acme-sde-pay", "exp-acme-sde-lock", "exp-acme-sde-onboard",
                "exp-acme-sde-notif", "exp-acme-sde-infra", "exp-acme-sde-agents",
            ]),
            "exp-acme-intern": SectionPatch(include=["exp-acme-intern-assets"]),
            "exp-uni-intern": SectionPatch(include=["exp-uni-intern-api"]),
            "prj-mentor": SectionPatch(include=["prj-mentor-apis", "prj-mentor-rag", "prj-mentor-match"]),
        },
    )
