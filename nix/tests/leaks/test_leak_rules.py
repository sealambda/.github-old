"""Tests of the leak rules: what each rule finds and what it leaves alone.

Every identifier here is false on purpose: the account `123456789012` is the
example of the AWS documentation, the organization is `acme`, and the hosts and
buckets are below `example`. The flake check does not scan this folder.
"""

import signal
import unittest
from types import FrameType

from leaks.rules import Policy, build_rules

POLICY = Policy(
    organization="acme",
    public_repositories=frozenset({".github", "hub"}),
    public_teams=frozenset({"maintainers"}),
)
"""A policy with two public repositories and one public team."""


def leaks(text: str) -> list[tuple[str, str]]:
    """Return the `(rule name, leaked text)` of each leak in `text`, sorted."""
    return sorted(
        (rule.name, leak.text)
        for rule in build_rules(POLICY)
        for leak in rule.find(text)
    )


def rule_names(text: str) -> set[str]:
    """Return the names of the rules that find a leak in `text`."""
    return {name for name, _ in leaks(text)}


def runner_labels(text: str) -> list[str]:
    """Return the text of each leak of the rule `runner-label`, sorted."""
    return [leaked for name, leaked in leaks(text) if name == "runner-label"]


class AwsAccountTest(unittest.TestCase):
    """The rule `aws-account`."""

    def test_twelve_digits_alone_are_an_account(self) -> None:
        """The plain and the dashed form are found, in prose and in a value."""
        for text in (
            "account 123456789012 runs it",
            'account_id = "123456789012"',
            "the account 1234-5678-9012.",
        ):
            with self.subTest(text=text):
                self.assertIn("aws-account", rule_names(text))

    def test_other_numbers_are_not_an_account(self) -> None:
        """A shorter or longer number, and digits inside a hash, are not found."""
        for text in (
            "12345678901 is one digit short",
            "1234567890123 is one digit long",
            "sha256-abc123456789012def",
            "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "lastModified: 1762819200",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])


class AwsResourceTest(unittest.TestCase):
    """The rule `aws-resource`."""

    def test_arn_and_endpoint_are_found(self) -> None:
        """An ARN of any service and any `amazonaws.com` host are found."""
        for text in (
            "arn:aws:iam::123456789012:role/deploy",
            "arn:aws-cn:sqs:cn-north-1:123456789012:queue",
            "123456789012.dkr.ecr.eu-west-1.amazonaws.com/app",
            "https://sts.eu-west-1.amazonaws.com",
        ):
            with self.subTest(text=text):
                self.assertIn("aws-resource", rule_names(text))

    def test_documentation_site_is_not_a_resource(self) -> None:
        """The AWS documentation and the word `arn` alone are not found."""
        for text in ("https://docs.aws.amazon.com/IAM/", "an arn of a role"):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_service_principal_has_one_label_and_is_public(self) -> None:
        """`sts.amazonaws.com` is public: a trust policy names it in every account."""
        for text in (
            "Principal: ec2.amazonaws.com",
            "audience sts.amazonaws.com.",
            "https://s3.amazonaws.com/",
            "Service: lambda.amazonaws.com.cn",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_path_style_bucket_address_is_found(self) -> None:
        """A path with a name after a one-label host names a bucket."""
        cases = {
            "https://s3.amazonaws.com/example-bucket/key": "s3.amazonaws.com",
            "https://s3-us-west-2.amazonaws.com/example-bucket/key": (
                "s3-us-west-2.amazonaws.com"
            ),
            r"https:\/\/s3.amazonaws.com\/example-bucket": "s3.amazonaws.com",
            "see s3.amazonaws.com%2Fexample-bucket": "s3.amazonaws.com",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("aws-resource", leaked)])

    def test_service_host_with_a_root_or_a_query_path_is_public(self) -> None:
        """A slash with no name after it is the root of the service."""
        for text in (
            "https://sts.amazonaws.com/",
            "https://sts.amazonaws.com/?Action=GetCallerIdentity",
            "sts.amazonaws.com/ is the endpoint",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_host_with_a_region_an_account_or_a_bucket_is_found(self) -> None:
        """Two or more labels before the domain name a region or a resource."""
        cases = {
            "ec2.eu-west-1.amazonaws.com": "ec2.eu-west-1.amazonaws.com",
            "uses my-bucket.s3.amazonaws.com/key": "my-bucket.s3.amazonaws.com",
            "dynamodb.cn-north-1.amazonaws.com.cn": (
                "dynamodb.cn-north-1.amazonaws.com.cn"
            ),
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("aws-resource", leaked)])

    def test_arn_of_an_aws_managed_policy_is_public(self) -> None:
        """The account field `aws` marks a policy that AWS owns."""
        for text in (
            "arn:aws:iam::aws:policy/ReadOnlyAccess",
            "arn:aws-cn:iam::aws:policy/service-role/Role",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_every_other_arn_is_found(self) -> None:
        """An ARN with another account, with no account, or with `aws` elsewhere."""
        for text in (
            "arn:aws:iam::210987654321:policy/aws",
            "arn:aws:s3:::name-of-a-bucket",
            "arn:aws:iam::awsx:policy/Name",
            "arn:aws:sqs:aws:queue",
        ):
            with self.subTest(text=text):
                self.assertIn("aws-resource", rule_names(text))


class BucketTest(unittest.TestCase):
    """The rule `bucket`."""

    def test_bucket_addresses_are_found(self) -> None:
        """An S3 address, an R2 address and an organization-prefixed name."""
        cases = {
            "substituters = s3://example-cache?region=eu": "s3://example-cache",
            "https://0a1b2c.r2.cloudflarestorage.com/state": (
                "0a1b2c.r2.cloudflarestorage.com"
            ),
            "https://pub-0a1b2c.r2.dev/file": "pub-0a1b2c.r2.dev",
            'bucket = "acme-tfstate"': "acme-tfstate",
            "the App acme-release-bot signs it": "acme-release-bot",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertIn(("bucket", leaked), leaks(text))

    def test_value_of_a_bucket_key_is_found_without_the_prefix(self) -> None:
        """A bucket name that lacks the organization prefix is found by its key."""
        cases = {
            'bucket = "state-files"': 'bucket = "state-files',
            "bucket: state-files": "bucket: state-files",
            "bucket_name = 'logs.example'": "bucket_name = 'logs.example",
            "bucket-name: logs42": "bucket-name: logs42",
            '"bucket": "state-files",': 'bucket": "state-files',
            "BUCKET_NAME=state-files": "BUCKET_NAME=state-files",
            "Bucket: state-files": "Bucket: state-files",
            "run --bucket state-files": "--bucket state-files",
            "run --bucket=state-files": "--bucket=state-files",
            'run --bucket "state-files"': '--bucket "state-files',
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                found = [value for name, value in leaks(text) if name == "bucket"]
                self.assertEqual(found, [leaked])

    def test_key_with_word_prefixes_or_camel_case_is_found(self) -> None:
        """A key may have prefixes before `bucket` and the suffix `name`.

        The prefixes join with `_` or `-`, and the camel-case forms start a new
        word with a capital letter.
        """
        cases = {
            "s3_bucket: x-y-z": "s3_bucket: x-y-z",
            "cache_bucket_name = abc": "cache_bucket_name = abc",
            "a-b-c-bucket-name: abc": "a-b-c-bucket-name: abc",
            "TF_STATE_BUCKET=abc": "TF_STATE_BUCKET=abc",
            "bucketName: abc": "bucketName: abc",
            "stateBucket: abc": "stateBucket: abc",
            "stateBucketName = 'abc-def'": "stateBucketName = 'abc-def",
            '"stateBucket": "abc"': 'stateBucket": "abc',
            "  my-stateBucketName:  abc": "my-stateBucketName:  abc",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                found = [value for name, value in leaks(text) if name == "bucket"]
                self.assertEqual(found, [leaked])

    def test_prefixed_key_with_an_organization_name_is_found_twice(self) -> None:
        """The key and the organization prefix each find the value."""
        found = [
            value
            for name, value in leaks('state_bucket = "acme-state-prod"')
            if name == "bucket"
        ]
        self.assertIn('state_bucket = "acme-state-prod', found)
        self.assertIn("acme-state-prod", found)

    def test_prefixed_key_with_a_reference_or_prose_is_not_found(self) -> None:
        """The exclusions of the plain key hold for every prefixed form."""
        for text in (
            "state_bucket = var.state_bucket",
            "s3_bucket = aws_s3_bucket.state.id",
            "s3_bucket: ${{ inputs.bucket }}",
            "stateBucket: ${BUCKET}",
            "stateBucketName: $BUCKET",
            "cache_bucket_name: ab",
            "bucketName: UPPER_CASE",
            "the state bucket is private",
            "state_bucket",
            "stateBucket and bucketName",
            "nobucket: abc",
            "stateBuckets: abc",
            "state_bucket_arn = abc",
            "bucketing: abc",
            "stateBucketNames: abc",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_references_and_prose_are_not_a_bucket_name(self) -> None:
        """A variable, an expression, a short value and prose name no bucket."""
        for text in (
            "bucket = var.state_bucket",
            "bucket = aws_s3_bucket.state.id",
            "bucket: ${{ inputs.bucket }}",
            'bucket = "${var.bucket}"',
            "bucket = ${BUCKET}",
            "bucket = $BUCKET",
            "--bucket $BUCKET",
            "--bucket ${{ vars.BUCKET }}",
            "bucket: ab",
            "bucket: UPPER_CASE",
            "the bucket is private",
            "a bucket name is a string",
            "the `--bucket` flag",
            "bucket",
            "my_bucket_name",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_flag_values_are_not_a_bucket_name(self) -> None:
        """A switch such as `create_bucket = true` names no bucket.

        The words are `true`, `false`, `null`, `none`, `yes`, `no`, `on` and
        `off`, in any letter case, quoted or not.
        """
        for text in (
            "create_bucket = true",
            "enable_bucket: false",
            "is_bucket: true",
            'use_bucket = "yes"',
            "bucket: true",
            "bucket = null",
            "bucket: none",
            "bucket: no",
            "bucket: on",
            "bucket: off",
            "bucket: TRUE",
            "bucket: False",
            "bucket = 'Yes'",
            '"bucket": true,',
            '"bucket": "false",',
            "--bucket false",
            "bucket: true.",
            "bucket: true, other",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_a_longer_word_that_starts_like_a_flag_value_is_found(self) -> None:
        """Only the whole word is a flag value: a name may start with one."""
        cases = {
            "bucket: trueish": "bucket: trueish",
            "bucket = nullable": "bucket = nullable",
            'bucket = "true-state"': 'bucket = "true-state',
            "bucket: yes.example": "bucket: yes.example",
            "bucket = off-site": "bucket = off-site",
            "bucket: none42": "bucket: none42",
            "create_bucket: nonexistent": "create_bucket: nonexistent",
            "--bucket true.example": "--bucket true.example",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                found = [value for name, value in leaks(text) if name == "bucket"]
                self.assertEqual(found, [leaked])

    def test_organization_name_without_the_prefix_form_is_not_found(self) -> None:
        """A suffix, a capitalized word and the bare name are not a resource."""
        for text in ("vale-style-acme", "an Acme-wide rule", "acme decides", "s3 only"):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])


class RunnerLabelTest(unittest.TestCase):
    """The rule `runner-label`."""

    def test_self_hosted_labels_of_runs_on_are_found(self) -> None:
        """Each label that is not hosted is a leak, in every form of the key."""
        cases = {
            "    runs-on: builder-large\n": ["builder-large"],
            "    runs-on: [self-hosted, linux]\n": [
                "[self-hosted, linux]",
                "linux",
                "self-hosted",
            ],
            'runs-on: \'["ubuntu-24.04", "gpu"]\'\n': ["gpu"],
            "    runs-on:\n      - self-hosted\n      - big # fast\n": [
                "big",
                "self-hosted",
            ],
            "    runs-on: { group: builders }\n": ["builders", "group"],
        }
        for text, labels in cases.items():
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), labels)

    def test_mapping_form_reports_the_group_and_the_labels(self) -> None:
        """The values of `group` and `labels` are private, the keys are not."""
        cases = {
            "runs-on:\n  group: builders\n": ["builders"],
            "runs-on:\n  labels: gpu\n": ["gpu"],
            "runs-on:\n  group: builders\n  labels: [gpu, linux]\nsteps:\n": [
                "builders",
                "gpu",
                "linux",
            ],
            "runs-on:\n  labels:\n    - gpu\n    - ubuntu-latest\n": ["gpu"],
            "    runs-on:\n      group: ${{ inputs.group }}\n": [],
            "runs-on:\n  group: builders\njobs-next: big\n": ["builders"],
        }
        for text, labels in cases.items():
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), labels)

    def test_mapping_form_stops_at_the_next_key(self) -> None:
        """A key at the indentation of `runs-on` is not a part of its value."""
        text = "    runs-on:\n      group: ubuntu-latest\n    labels: other\n"
        self.assertEqual(runner_labels(text), [])

    def test_literals_inside_an_expression_are_labels(self) -> None:
        """The quoted strings of an expression are read, its names are not."""
        cases = {
            "runs-on: ${{ c && 'ubuntu-latest' || 'self-hosted' }}\n": ["self-hosted"],
            'runs-on: ${{ inputs.big && "gpu" || "macos-15" }}\n': ["gpu"],
            "runs-on: ${{ fromJSON('[\"big\"]') }}\n": ["big"],
            "runs-on: ${{ c && 'ubuntu-latest' || 'windows-2025' }}\n": [],
            "runs-on: ${{ inputs.self-hosted && matrix.os }}\n": [],
        }
        for text, labels in cases.items():
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), labels)

    def test_hosted_prefix_with_an_expression_is_hosted(self) -> None:
        """`ubuntu-${{ ... }}` is hosted, and another prefix is not."""
        cases = {
            "runs-on: ubuntu-${{ matrix.version }}\n": [],
            "runs-on: macos-${{ matrix.version }}-large\n": [],
            "runs-on: windows-${{ matrix.version }}\n": [],
            "runs-on: ${{ matrix.os }}-large\n": [],
            "runs-on: builder-${{ matrix.version }}\n": [
                "builder-${{ matrix.version }}"
            ],
        }
        for text, labels in cases.items():
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), labels)

    def test_documented_shapes_of_hosted_labels_are_public(self) -> None:
        """The shapes of the tables of GitHub, for any version, are hosted.

        The source is the page "GitHub-hosted runners" and the page "Larger
        runners" of the GitHub documentation. The versions here include some
        that do not exist yet, because the rule reads the shape.
        """
        for label in (
            "ubuntu-latest",
            "ubuntu-slim",
            "ubuntu-24.04",
            "ubuntu-24.04-arm",
            "ubuntu-30.04",
            "windows-latest",
            "windows-2025",
            "windows-2025-vs2026",
            "windows-2031",
            "windows-11-arm",
            "windows-11-vs2026-arm",
            "macos-latest",
            "macos-15",
            "macos-15-intel",
            "macos-15-large",
            "macos-15-xlarge",
            "macos-latest-large",
            "macos-latest-xlarge",
            "macos-31",
            "xcode-27",
            "xcode-27-xlarge",
        ):
            with self.subTest(label=label):
                self.assertEqual(runner_labels(f"runs-on: {label}\n"), [])

    def test_other_labels_with_a_hosted_prefix_are_found(self) -> None:
        """A suffix or a version that no table of GitHub has names a private runner."""
        for label in (
            "ubuntu-acme-pool",
            "macos-selfhosted",
            "ubuntu-latest-acme",
            "ubuntu-24.04-gpu",
            "ubuntu-24.04-arm-big",
            "ubuntu-slim-large",
            "ubuntu-24",
            "ubuntu-",
            "windows-latest-big",
            "windows-2025-acme",
            "windows-11",
            "macos-15-pool",
            "macos-latest-intel",
            "macos-selfhosted-15",
            "xcode-27-large",
            "xcode-latest",
            "Ubuntu-acme-pool",
            "MACOS-SelfHosted",
        ):
            with self.subTest(label=label):
                self.assertEqual(runner_labels(f"runs-on: {label}\n"), [label])

    def test_hosted_labels_have_any_letter_case(self) -> None:
        """A hosted label in any letter case is hosted: labels ignore case.

        The source is the note "Labels are case-insensitive" of the page "Using
        labels with self-hosted runners" of the GitHub documentation.
        """
        for label in (
            "Ubuntu-latest",
            "UBUNTU-LATEST",
            "ubuntu-24.04-ARM",
            "Windows-2025-VS2026",
            "macOS-15-XLarge",
            "macos-Latest-Large",
            "XCode-27",
            "ubuntu-${{ matrix.v }}-ARM",
            "Windows-${{ matrix.v }}-${{ matrix.size }}",
        ):
            with self.subTest(label=label):
                self.assertEqual(runner_labels(f"runs-on: {label}\n"), [])

    def test_expression_after_a_hosted_prefix_allows_only_hosted_suffixes(self) -> None:
        """The expression stands for a version, so a name after it is a leak."""
        cases = {
            "runs-on: ubuntu-${{ matrix.v }}\n": [],
            "runs-on: ubuntu-${{ matrix.v }}-arm\n": [],
            "runs-on: ubuntu-24.${{ matrix.v }}\n": [],
            "runs-on: windows-${{ matrix.v }}-vs${{ matrix.y }}-arm\n": [],
            "runs-on: macos-${{ matrix.v }}-xlarge\n": [],
            "runs-on: ubuntu-${{ matrix.v }}-${{ matrix.size }}\n": [],
            "runs-on: ubuntu-${{ matrix.v }}-intel\n": [],
            "runs-on: macos-${{ matrix.v }}-${{ matrix.size }}-arm\n": [],
            "runs-on: ubuntu-${{ matrix.v }}-\n": ["ubuntu-${{ matrix.v }}-"],
            "runs-on: ubuntu-${{ matrix.v }}-acme-${{ matrix.size }}\n": [
                "ubuntu-${{ matrix.v }}-acme-${{ matrix.size }}"
            ],
            "runs-on: ubuntu-${{ matrix.v }}-acme-pool\n": [
                "ubuntu-${{ matrix.v }}-acme-pool"
            ],
            "runs-on: macos-${{ matrix.v }}-selfhosted\n": [
                "macos-${{ matrix.v }}-selfhosted"
            ],
            "runs-on: ubuntu-acme-${{ matrix.v }}\n": ["ubuntu-acme-${{ matrix.v }}"],
        }
        for text, labels in cases.items():
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), labels)

    def test_flow_list_over_several_lines_is_read(self) -> None:
        """The labels of a list that opens on the key line are found."""
        text = "runs-on: [\n  self-hosted,\n  linux # note\n]\nsteps: [x]\n"
        self.assertEqual(runner_labels(text), ["linux", "self-hosted"])

    def test_flow_list_ends_at_its_bracket(self) -> None:
        """The text after the closing bracket, and a closed list, hold no label."""
        for text in (
            "runs-on: [\n  ubuntu-latest\n] other words here\n",
            "runs-on: [ubuntu-latest]\nnext: words\n",
            "runs-on: [\nruns-on: ubuntu-latest\n  other\n]\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(runner_labels(text), [])

    def test_lines_that_end_with_crlf_are_read(self) -> None:
        """A block list with CRLF line ends gives the same labels as LF."""
        text = "runs-on:\r\n  - self-hosted\r\n  - big\r\n  - ubuntu-latest\r\n"
        self.assertEqual(runner_labels(text), ["big", "self-hosted"])
        self.assertEqual(
            runner_labels("runs-on: ubuntu-latest\r\nsteps:\r\n"),
            [],
        )

    def test_comment_after_the_key_is_not_a_label(self) -> None:
        """`runs-on: # comment` starts a block, and the comment has no label."""
        text = "runs-on: # the runner of this job\n  - self-hosted\n  # note\n  - big\n"
        self.assertEqual(runner_labels(text), ["big", "self-hosted"])
        self.assertEqual(runner_labels("runs-on: # the runner words\n"), [])

    def test_each_key_of_a_line_is_read(self) -> None:
        """Two code spans with a key on one line give the labels of both."""
        text = "Use `runs-on: ubuntu-latest` or `runs-on: gpu-box` here.\n"
        self.assertEqual(runner_labels(text), ["gpu-box"])
        self.assertEqual(
            runner_labels("Use `runs-on: ubuntu-latest` or `runs-on: macos-15`.\n"), []
        )

    def test_comment_inside_a_block_list_is_not_a_label(self) -> None:
        """A comment on an item line, and a comment line, hold no label."""
        text = "runs-on:\n  - # note words\n#column zero words\n  - big # more words\n"
        self.assertEqual(runner_labels(text), ["big"])

    def test_list_items_at_the_indentation_of_the_key_are_read(self) -> None:
        """YAML allows `- item` at the column of its key."""
        self.assertEqual(runner_labels("runs-on:\n- big\nsteps:\n- x\n"), ["big"])

    def test_hosted_labels_and_expressions_are_not_found(self) -> None:
        """Hosted labels, an expression and the key of an input are public."""
        for text in (
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-24.04-arm # hosted\n",
            'runs-on: \'["macos-15", "windows-2025"]\'\n',
            "    runs-on: ${{ fromJSON(inputs.runs-on) }}\n",
            "    runs-on: ${{ matrix.os }}\n",
            "      runs-on:\n        description: The labels.\n",
            "Set `runs-on: ubuntu-latest` in the job.\n",
            "The `runs-on` input is optional.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_runner_type_and_label_list_are_found_anywhere(self) -> None:
        """A `<project>-<architecture>-<size>` type and a self-hosted list."""
        self.assertEqual(
            leaks("The type app-x64-small starts in 22 s."),
            [("runner-label", "app-x64-small")],
        )
        self.assertEqual(
            leaks("default: '[\"self-hosted\"]'"),
            [("runner-label", '["self-hosted"]')],
        )

    def test_self_hosted_as_a_word_is_not_found(self) -> None:
        """A page may say that a repository uses self-hosted runners."""
        self.assertEqual(leaks("Private repositories use self-hosted runners."), [])

    def test_self_hosted_as_a_list_element_is_found(self) -> None:
        """The bracket text is the leak, whatever else the list holds."""
        cases = {
            "[self-hosted]": "[self-hosted]",
            "[ self-hosted , linux ]": "[ self-hosted , linux ]",
            "labels: [linux, 'self-hosted', x64]": "[linux, 'self-hosted', x64]",
            "default: '[\"self-hosted\"]'": '["self-hosted"]',
            "[a, self-hosted]": "[a, self-hosted]",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("runner-label", leaked)])

    def test_self_hosted_in_the_text_of_a_link_is_not_found(self) -> None:
        """Prose in brackets, and a list across lines or too far, hold no element."""
        for text in (
            "[about self-hosted runners](https://example.com/runners)",
            "[self-hosted runners](https://example.com/runners)",
            "[the self-hosted label]",
            "[docs], self-hosted, [more]",
            "[self-hosted\nlinux]",
            "[" + "x" * 300 + ", self-hosted]",
            "[self-hosted, " + "x" * 300 + "]",
        ):
            with self.subTest(text=text[:40]):
                self.assertEqual(leaks(text), [])

    def test_runner_type_is_not_found_in_a_package_name(self) -> None:
        """A name after `@` or `/` is a package, as in a lock file."""
        for text in (
            "@rollup/rollup-linux-x64-gnu",
            '"node_modules/@rollup/rollup-linux-arm64-musl": {',
            "node_modules/@esbuild/darwin-arm64/bin",
            "path/to/app-x64-small",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_runner_type_after_a_space_or_a_quote_is_found(self) -> None:
        """The same shape elsewhere stays a finding: the limit of the rule."""
        for text in ("use app-x64-small", 'type: "app-arm64-large"', "(app-x64-xl)"):
            with self.subTest(text=text):
                self.assertEqual(rule_names(text), {"runner-label"})


class InternalHostTest(unittest.TestCase):
    """The rule `internal-host`."""

    def test_private_names_and_addresses_are_found(self) -> None:
        """Private suffixes, a Tailscale name, private IPv4 and a subdomain."""
        cases = {
            "ssh db.example.internal": "db.example.internal",
            "http://printer.local/": "printer.local",
            "host box.tail0a1b2.ts.net": "box.tail0a1b2.ts.net",
            "listen 10.0.0.5:443": "10.0.0.5",
            "at 192.168.1.20.": "192.168.1.20",
            "via 172.16.0.1": "172.16.0.1",
            "peer 100.64.0.7": "100.64.0.7",
            "https://grafana.acme.example/": "grafana.acme.example",
            "mail ops@mail.Acme.com": "mail.Acme.com",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("internal-host", leaked)])

    def test_public_names_and_addresses_are_not_found(self) -> None:
        """File names, method calls, public addresses and the public site."""
        for text in (
            "edit settings.local.json",
            "the file .envrc.local",
            "threading.local()",
            "version 10.2.3",
            "dns 8.8.8.8 and 172.32.0.1 and 100.128.0.1",
            "https://www.acme.com and https://acme.com/about",
            "write to security@acme.com",
            "an internal tool and a local file",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])


class GithubAppTest(unittest.TestCase):
    """The rule `github-app`."""

    def test_app_identifiers_are_found(self) -> None:
        """Client identifiers, numeric identifiers by key and a bot address."""
        for text in (
            "client Iv1.0123456789abcdef",
            "client Iv23liABCDEFGH012345",
            "app_id: 123456",
            'APP_ID="1234567"',
            "installation-id = 12345678",
            "`client id`: 98765",
            "https://github.com/settings/installations/12345678",
            "123456+release-helper[bot]@users.noreply.github.com",
        ):
            with self.subTest(text=text):
                self.assertEqual(rule_names(text), {"github-app"})

    def test_commit_address_of_a_public_bot_is_not_found(self) -> None:
        """The three bot accounts that every repository has are public."""
        for slug in ("github-actions", "renovate", "dependabot"):
            for text in (
                f"user.email 12345+{slug}[bot]@users.noreply.github.com",
                f"Author: 1+{slug.upper()}[bot]@users.noreply.github.com",
            ):
                with self.subTest(text=text):
                    self.assertEqual(leaks(text), [])

    def test_commit_address_of_another_bot_is_found(self) -> None:
        """A slug that is not one of the three public ones names a private App."""
        for slug in ("release-helper", "renovate-pro", "my-dependabot", "actions"):
            text = f"12345+{slug}[bot]@users.noreply.github.com"
            with self.subTest(slug=slug):
                self.assertEqual(leaks(text), [("github-app", text)])

    def test_keys_without_a_number_are_not_found(self) -> None:
        """A key with a variable, and a word that only ends in `id`, are public."""
        for text in (
            "app-id: ${{ vars.APP_ID }}",
            "app_id = var.app_id",
            "grid: 12345",
            "the App id of the installation",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])


class RepositoryTest(unittest.TestCase):
    """The rule `repository`."""

    def test_names_off_the_public_list_are_found(self) -> None:
        """Every form of a repository name, and a team that is not public."""
        cases = {
            "see acme/billing for it": "acme/billing",
            "`Acme/Billing` decided": "Acme/Billing",
            "https://github.com/acme/billing/pull/3": "github.com/acme/billing",
            "git@github.com:acme/billing.git": "github.com:acme/billing.git",
            "hub.url = github:acme/billing": "acme/billing",
            "https://api.github.com/repos/acme/billing": "/repos/acme/billing",
            "image ghcr.io/acme/billing:1": "ghcr.io/acme/billing",
            "* @acme/platform-team": "@acme/platform-team",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_public_names_are_not_found(self) -> None:
        """The public list, in every form and letter case, and a public team."""
        for text in (
            "see acme/hub.",
            "uses: acme/.github/.github/workflows/x.yml@main",
            "https://github.com/Acme/HUB/blob/main/README.md",
            "git@github.com:acme/.github.git",
            "* @acme/maintainers",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_team_addresses_off_the_public_list_are_found(self) -> None:
        """The web and API addresses of a team, plain, escaped and with a host."""
        cases = {
            "https://github.com/orgs/acme/teams/billing": "orgs/acme/teams/billing",
            "https://api.github.com/orgs/Acme/teams/billing/repos": (
                "orgs/Acme/teams/billing"
            ),
            "gh api /orgs/acme/teams/billing/members": "orgs/acme/teams/billing",
            "gh api orgs/acme/teams/billing": "orgs/acme/teams/billing",
            r"https:\/\/github.com\/orgs\/acme\/teams\/billing": (
                r"orgs\/acme\/teams\/billing"
            ),
            "https%3A%2F%2Fgithub.com%2Forgs%2Facme%2Fteams%2Fbilling": (
                "orgs%2Facme%2Fteams%2Fbilling"
            ),
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_public_team_and_other_addresses_are_not_found(self) -> None:
        """A public team, another owner, another page and a longer word pass."""
        for text in (
            "https://github.com/orgs/acme/teams/maintainers",
            "https://github.com/orgs/Acme/teams/Maintainers/members",
            "https://github.com/orgs/example/teams/billing",
            "https://github.com/orgs/acme/people",
            "https://github.com/myorgs/acme/teams/billing",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_more_forms_of_an_address_are_found(self) -> None:
        """The API without a first slash, raw content, any letter case, any host."""
        cases = {
            "gh api repos/acme/billing/pulls": "repos/acme/billing",
            "gh api -X GET repos/Acme/Billing": "repos/Acme/Billing",
            "https://raw.githubusercontent.com/acme/billing/main/a": (
                "raw.githubusercontent.com/acme/billing"
            ),
            "https://objects.githubusercontent.com/acme/billing": (
                "objects.githubusercontent.com/acme/billing"
            ),
            "https://GitHub.com/acme/billing": "GitHub.com/acme/billing",
            "https://GITHUB.COM/ACME/billing": "GITHUB.COM/ACME/billing",
            "https://gitlab.com/acme/billing": "gitlab.com/acme/billing",
            "git@git.example.org:acme/billing.git": "git.example.org:acme/billing.git",
            "ssh://git@github.com:22/acme/billing": "github.com:22/acme/billing",
            "docker pull registry.example.net/acme/billing:1": (
                "registry.example.net/acme/billing"
            ),
            "see /acme/billing": "/acme/billing",
            '"/acme/billing/blob/main"': "/acme/billing",
            "(/acme/billing)": "/acme/billing",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_public_names_are_not_found_in_the_new_forms(self) -> None:
        """A public repository stays public in every form of an address."""
        for text in (
            "gh api repos/acme/hub/pulls",
            "https://raw.githubusercontent.com/acme/.github/main/a",
            "https://GitHub.com/ACME/Hub",
            "see /acme/hub",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_folders_and_other_owners_are_not_a_repository_in_any_form(self) -> None:
        """Only an address, the API path or a leading slash makes a repository."""
        for text in (
            "vale/Acme/CurrentState.yml",
            "share/vale/styles/Acme",
            "./acme/billing and ../acme/billing",
            "~/acme/billing",
            "/usr/share/acme/billing",
            "$HOME/acme/billing",
            "example/acme/billing",
            "myrepos/acme/billing",
            "https://example.com/about/acme",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_pages_address_and_escaped_slashes_are_found(self) -> None:
        """A Pages address, a JSON slash and a URL-encoded slash name a repository."""
        cases = {
            "https://acme.github.io/billing/": "acme.github.io/billing",
            "ACME.GitHub.io/Billing": "ACME.GitHub.io/Billing",
            '"repo": "acme\\/billing"': "acme\\/billing",
            "https:\\/\\/github.com\\/acme\\/billing": "github.com\\/acme\\/billing",
            "https:\\/\\/api.github.com\\/repos\\/acme\\/billing\\/pulls": (
                "repos\\/acme\\/billing"
            ),
            "\\/acme\\/billing": "\\/acme\\/billing",
            "@acme\\/platform-team": "@acme\\/platform-team",
            "repo=acme%2Fbilling": "acme%2Fbilling",
            "repo=acme%2fbilling": "acme%2fbilling",
            "repo=ACME%2FBilling": "ACME%2FBilling",
            "https%3A%2F%2Fgithub.com%2Facme%2Fbilling%2Fpull%2F3": (
                "github.com%2Facme%2Fbilling"
            ),
            "q=%2Facme%2Fbilling": "%2Facme%2Fbilling",
            "@acme%2Fplatform-team": "@acme%2Fplatform-team",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_public_names_stay_public_in_the_new_forms(self) -> None:
        """The public list holds in a Pages address and in the escaped forms."""
        for text in (
            "https://acme.github.io/hub/",
            "https://acme.github.io/.github",
            "https://acme.github.io and https://acme.github.io/",
            '"repo": "acme\\/hub"',
            "https:\\/\\/github.com\\/ACME\\/Hub",
            "https:\\/\\/github.com\\/acme\\/.github",
            "@acme\\/maintainers",
            "repo=acme%2Fhub",
            "repo=acme%2fHUB",
            "https%3A%2F%2Fgithub.com%2Facme%2Fhub%2Fpull%2F3",
            "@acme%2Fmaintainers",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_folders_and_other_owners_are_not_found_in_the_new_forms(self) -> None:
        """Only an address, the API path or a leading slash makes a repository."""
        for text in (
            "example\\/acme\\/billing",
            "example%2Facme%2Fbilling",
            "styles\\/Acme\\/rule.yml",
            "myrepos\\/acme\\/billing",
            "notacme.github.io/billing",
            "example.github.io/acme",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_encoded_delimiter_before_the_organization_is_found(self) -> None:
        """A percent-encoded colon, space, quote or plus does not hide the name."""
        cases = {
            "https://x.com/search?q=repo%3Aacme%2Fbilling": "acme%2Fbilling",
            "q=org%3Aacme+repo%3Aacme%2Fbilling": "acme%2Fbilling",
            "q=repo%3aacme%2fbilling": "acme%2fbilling",
            "q=repo%3AACME%2FBilling": "ACME%2FBilling",
            "q=x+acme%2Fbilling": "acme%2Fbilling",
            "q=%20acme%2Fbilling": "acme%2Fbilling",
            "q=%22acme%2Fbilling%22": "acme%2Fbilling",
            "q=repo%3Aacme/billing": "acme/billing",
            "q=repo%3A%2Facme%2Fbilling": "%2Facme%2Fbilling",
            "q=repo%3Aacme.github.io%2Fbilling": "acme.github.io%2Fbilling",
            "q=x%3Arepos%2Facme%2Fbilling": "repos%2Facme%2Fbilling",
            "q=x%3Arepos/acme/billing": "repos/acme/billing",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_encoded_delimiter_before_a_public_name_is_not_found(self) -> None:
        """The public list holds after an encoded delimiter."""
        for text in (
            "q=repo%3Aacme%2Fhub",
            "q=org%3Aacme+repo%3Aacme%2FHUB",
            "q=repo%3Aacme/.github",
            "q=repo%3Aacme.github.io%2Fhub",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_encoded_name_character_or_slash_is_not_a_delimiter(self) -> None:
        """`%2D`, `%2E`, `%5F`, `%7E` and `%2F` come before a longer word or path."""
        for text in (
            "example%2Facme%2Fbilling",
            "example%2facme%2fbilling",
            "example%2Facme/billing",
            "example%2Dacme%2Fbilling",
            "example%2dacme/billing",
            "example%2Eacme%2Fbilling",
            "example%5Facme%2Fbilling",
            "example%5facme/billing",
            "example%7Eacme%2Fbilling",
            "example%7eacme/billing",
            "example%2Eacme.github.io/billing",
            "example%5Facme.github.io%2Fbilling",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_pages_address_with_an_escaped_slash_is_found(self) -> None:
        """A JSON slash and a URL-encoded slash after `.github.io` name a repository."""
        cases = {
            "https:\\/\\/acme.github.io\\/billing": "acme.github.io\\/billing",
            "acme.github.io\\/billing": "acme.github.io\\/billing",
            "ACME.GitHub.io\\/Billing\\/x": "ACME.GitHub.io\\/Billing",
            "https%3A%2F%2Facme.github.io%2Fbilling": "acme.github.io%2Fbilling",
            "acme.github.io%2fbilling%2Fx": "acme.github.io%2fbilling",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [("repository", leaked)])

    def test_pages_address_with_an_escaped_slash_stays_public_or_foreign(self) -> None:
        """The public list holds, and another owner or a longer label is not read."""
        for text in (
            "https:\\/\\/acme.github.io\\/hub",
            "https:\\/\\/acme.github.io\\/.github",
            "https:\\/\\/acme.github.io\\/ and acme.github.io\\/",
            "https%3A%2F%2Facme.github.io%2Fhub",
            "https%3A%2F%2Facme.github.io%2F",
            "notacme.github.io\\/billing",
            "notacme.github.io%2Fbilling",
            "example.github.io\\/acme",
            "example.github.io%2Facme",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])

    def test_a_longer_name_is_not_a_public_name(self) -> None:
        """`hub-test` is not `hub`: the whole name is compared."""
        self.assertEqual(leaks("acme/hub-test"), [("repository", "acme/hub-test")])

    def test_folder_and_other_owner_are_not_a_repository(self) -> None:
        """A folder named as the organization, and another owner, are public."""
        for text in (
            "vale/Acme/CurrentState.yml",
            "share/vale/styles/Acme",
            "other/billing and example/acme/billing",
        ):
            with self.subTest(text=text):
                self.assertEqual(leaks(text), [])


class RuleTimeTest(unittest.TestCase):
    """The time of every rule grows in step with the size of a line."""

    TIME_LIMIT_SECONDS = 10.0

    PATHOLOGICAL_LINES = {
        "digits": "1" * 1_000_000,
        "brackets": "[" * 1_000_000,
        "unclosed expressions": "runs-on: " + "${{ " * 250_000,
        "unclosed flow lists": "runs-on: " + "[" * 1_000_000,
        "labels without a list": "[self-hosted, " * 70_000,
        "dotted labels": "a." * 500_000,
        "repeated keys": "runs-on: " * 110_000,
        "keys in code spans": "`runs-on:" * 110_000,
        "keys with a comment": "runs-on: #" * 100_000,
        "bucket key prefixes": "a-" * 500_000,
        "bucket key camel case": "aB" * 500_000,
        "bucket key separators": "-" * 1_000_000,
        "escaped slashes": "\\/" * 500_000,
        "encoded slashes": "%2F" * 330_000,
        "encoded hosts": "%2Fa." * 200_000,
        "pages addresses": "acme.github.io/" * 70_000,
        "encoded delimiters": "%3A" * 330_000,
        "encoded delimiters before a name": "%3Aacme" * 140_000,
        "escaped pages addresses": "acme.github.io\\/" * 65_000,
        "encoded pages addresses": "acme.github.io%2F" * 60_000,
        "bucket flag values": "x_bucket = true " * 62_000,
    }

    @unittest.skipUnless(hasattr(signal, "setitimer"), "needs POSIX interval timers")
    def test_one_megabyte_line_is_scanned_in_linear_time(self) -> None:
        """A line of one megabyte must not make a rule rescan its rest per character.

        This test uses a time limit because the failure it guards against is a
        slow scan, not a wrong result: a pattern that rescans the line from
        each digit, each bracket or each `${{` needs hours on these lines, and
        a plain assertion would hang the whole run. A timer signal turns the
        hang into a failure. The limit is far above the time of a linear scan,
        which is below one second, so a slow machine does not fail the test.
        """
        for name, text in self.PATHOLOGICAL_LINES.items():
            with self.subTest(line=name):
                self.leaks_within_limit(text)

    @unittest.skipUnless(hasattr(signal, "setitimer"), "needs POSIX interval timers")
    def test_many_lines_that_open_a_list_are_scanned_in_linear_time(self) -> None:
        """Lines that each open a list or a block do not read the rest of the file.

        This test uses a time limit for the reason that the test above gives.
        """
        for name, text in {
            "flow lists": "runs-on: [\n" * 100_000,
            "blocks": "runs-on:\n" + "  x\n" * 300_000,
        }.items():
            with self.subTest(lines=name):
                self.leaks_within_limit(text)

    def leaks_within_limit(self, text: str) -> list[tuple[str, str]]:
        """Scan `text` with every rule and fail the test when it takes too long."""

        def on_timeout(_signal: int, _frame: FrameType | None) -> None:
            self.fail(f"the scan took more than {self.TIME_LIMIT_SECONDS} seconds")

        previous = signal.signal(signal.SIGALRM, on_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.TIME_LIMIT_SECONDS)
        try:
            return leaks(text)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    unittest.main()
