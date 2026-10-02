"""Regression tests for release isolation and Gitflow merge boundaries."""

from __future__ import annotations

import unittest

from scripts.check_gitflow import _policy_error


class GitflowPolicyTests(unittest.TestCase):
    def test_release_and_hotfix_reach_both_integration_branches(self) -> None:
        for head in ("release/manuscript-rc2", "hotfix/v0.2.1"):
            for base in ("main", "develop"):
                with self.subTest(base=base, head=head):
                    self.assertIsNone(_policy_error(base, head))

    def test_work_branches_cannot_bypass_release_into_main(self) -> None:
        for head in (
            "feature/maude-durations",
            "fix/temporal-cutoff",
            "chore/consolidation-post-rc1",
            "develop",
            "release-impostor/v0.2.1",
        ):
            with self.subTest(head=head):
                self.assertIsNotNone(_policy_error("main", head))

    def test_stabilization_accepts_hotfix_backports_but_not_new_features(self) -> None:
        self.assertIsNone(_policy_error("release/manuscript-rc2", "hotfix/v0.2.1"))
        self.assertIsNone(_policy_error("release/manuscript-rc2", "fix/metadata"))
        self.assertIsNone(_policy_error("hotfix/v0.2.1", "chore/release-notes"))
        self.assertIsNotNone(_policy_error("release/manuscript-rc2", "feature/new-model"))
        self.assertIsNotNone(_policy_error("hotfix/v0.2.1", "feature/new-model"))
        self.assertIsNotNone(_policy_error("hotfix/v0.2.1", "release/manuscript-rc2"))

    def test_only_supported_branch_names_and_targets_are_accepted(self) -> None:
        self.assertIsNone(_policy_error("develop", "feature/maude-durations"))
        for head in ("feature/", "release/RC2", "release/v0.2.1/nested", "fix/a\n"):
            with self.subTest(head=head):
                self.assertIsNotNone(_policy_error("develop", head))
        self.assertIsNotNone(_policy_error("feature/new-task", "fix/temporal-cutoff"))
        self.assertIsNotNone(_policy_error("release/", "fix/temporal-cutoff"))
        self.assertIsNotNone(_policy_error("develop", "develop"))

    def test_main_resynchronization_only_targets_develop(self) -> None:
        self.assertIsNone(_policy_error("develop", "main"))
        self.assertIsNotNone(_policy_error("release/manuscript-rc2", "main"))
        self.assertIsNotNone(_policy_error("main", "main"))


if __name__ == "__main__":
    unittest.main()
