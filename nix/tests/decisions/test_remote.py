"""Tests for the repository name and the permalink from the `origin` URL."""

import unittest

from decisions.remote import parse_github_remote, permalink, redact_userinfo


class ParseGithubRemoteTest(unittest.TestCase):
    """The URL forms of GitHub give `owner/name`."""

    def test_accepted_forms(self) -> None:
        """Short SSH, HTTPS and SSH URLs, with and without `.git`."""
        forms = [
            "git@github.com:acme/hub.git",
            "git@github.com:acme/hub",
            "https://github.com/acme/hub.git",
            "https://github.com/acme/hub",
            "https://github.com/acme/hub/",
            "ssh://git@github.com/acme/hub.git",
            "ssh://git@github.com:22/acme/hub.git",
            "https://token@github.com/acme/hub.git",
            "git://github.com/acme/hub.git",
            "HTTPS://GitHub.com/acme/hub",
        ]
        for url in forms:
            with self.subTest(url=url):
                self.assertEqual(parse_github_remote(url), "acme/hub")

    def test_dots_dashes_and_underscores_stay_in_names(self) -> None:
        """A name may hold dots, so only a final `.git` is a suffix."""
        self.assertEqual(
            parse_github_remote("git@github.com:example/.github.git"),
            "example/.github",
        )
        self.assertEqual(
            parse_github_remote("https://github.com/a_b/c-d.e"), "a_b/c-d.e"
        )

    def test_surrounding_whitespace_is_ignored(self) -> None:
        """`git remote get-url` output ends with a newline."""
        self.assertEqual(
            parse_github_remote("https://github.com/acme/hub.git\n"), "acme/hub"
        )

    def test_other_hosts_and_shapes_are_rejected(self) -> None:
        """Another host, a missing repository and a local path are errors."""
        rejected = [
            "git@gitlab.com:acme/hub.git",
            "https://example.com/acme/hub.git",
            "https://github.com/acme",
            "https://github.com/acme/hub/tree/main",
            "https://github.com.evil.example/acme/hub",
            "/srv/git/hub.git",
            "",
        ]
        for url in rejected:
            with (
                self.subTest(url=url),
                self.assertRaisesRegex(ValueError, "not a github.com"),
            ):
                parse_github_remote(url)


class RedactUserinfoTest(unittest.TestCase):
    """A URL that an error message shows never carries a user name or a token."""

    def test_error_text_hides_the_credentials(self) -> None:
        """The `ValueError` of a rejected URL names the host and the path only."""
        urls = [
            "https://x-access-token:ghs_SECRET@gitlab.example.com/acme/hub.git",
            "https://x-access-token:ghs_SECRET@github.com/acme",
            "https://user:pa/ss_SECRET@example.com/acme/hub.git",
            "ssh://ghs_SECRET@gitlab.example.com/acme/hub.git",
            "ghs_SECRET@gitlab.example.com:acme/hub.git",
        ]
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as caught:
                    parse_github_remote(url)
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertIn("not a github.com repository URL", str(caught.exception))

    def test_redacted_forms(self) -> None:
        """Everything before the last `@` becomes `***`; the rest stays."""
        cases = {
            "https://x-access-token:ghs_SECRET@github.com/acme": (
                "https://***@github.com/acme"
            ),
            "git@gitlab.com:acme/hub.git": "***@gitlab.com:acme/hub.git",
            "https://example.com/acme/hub.git": "https://example.com/acme/hub.git",
            "/srv/git/hub.git": "/srv/git/hub.git",
            "  https://t@example.com/a/b\n": "https://***@example.com/a/b",
            "": "",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(redact_userinfo(url), expected)


class PermalinkTest(unittest.TestCase):
    """The permalink follows the formula of the reference page."""

    def test_formula(self) -> None:
        """Repository, commit and path make the blob URL."""
        self.assertEqual(
            permalink("acme/hub", "ab" * 20, "docs/decisions/0001-x.md"),
            f"https://github.com/acme/hub/blob/{'ab' * 20}/docs/decisions/0001-x.md",
        )


if __name__ == "__main__":
    unittest.main()
