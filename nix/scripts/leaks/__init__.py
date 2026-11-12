"""Find private facts of the organization in a public source tree.

The hub is public, so it holds no account identifier, bucket, runner label,
internal host name or GitHub App identifier, and it names only the public
repositories of the organization. `leaks.rules` holds the patterns,
`leaks.scan` applies them to a tree, and `leaks.cli` is the command line.
"""
