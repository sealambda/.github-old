# Security policy

This policy describes how to report a vulnerability to Sealambda and how
Sealambda handles the report. It is a coordinated vulnerability disclosure
policy, modeled on ISO/IEC 29147.

## Scope

The policy covers the code in Sealambda's public repositories, at the latest
commit of `main`. Only that code receives security fixes.

## How to report

Report a vulnerability with
[GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on the affected repository. Never report it in a public issue, pull request
or discussion.

1. Open the **Security** tab of the repository. The page
   `https://github.com/sealambda/<repository>/security/advisories/new` opens
   the form directly.
2. Select **Report a vulnerability**, fill in the form and submit it.

## What to include

- The affected component.
- The version or commit.
- The steps to reproduce the vulnerability.
- The impact.

## What to expect

These are response targets, not guarantees:

- The maintainers acknowledge the report within 5 business days.
- After that, they send status updates until the report is closed.
- The default date for coordinated disclosure is 90 days after the report, or
  earlier when a fix ships. The maintainers agree on the date with the
  reporter.

## Good-faith guidelines

Research follows this policy when it keeps to these rules:

- Test only your own accounts and data.
- Access no more data than a proof needs, and keep none of it.
- Do not run denial-of-service, social-engineering or physical tests.
- Stop and report at once.

## Credit

The advisory credits the reporter if the reporter wants it. Sealambda pays no
bounty.

## Legal

Sealambda appreciates good-faith research that follows this policy and will
work with the reporter. This policy gives no authorization beyond what the law
already allows. It makes no safe-harbor promise.
