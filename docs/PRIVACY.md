# Release privacy

This repository was prepared as a new Git history. It does not carry the private
source repository's commits, contributors, discussions, raw API responses,
article abstracts, local review ledgers, or machine paths.

Commit author and committer identities use the neutral project name and an address
under the reserved `example.invalid` domain. This address is not a contact channel.
Examples and test abstracts are synthetic. Personal credentials are read only from
environment variables. Local run folders are ignored by Git.

GitHub ownership and repository activity remain visible under the owning account
if the repository is published. Anonymized contents and Git author fields do not
hide the repository owner, pusher, or platform activity. Aggregate journal coverage
is retained to explain the evidence and limitations; such statistics can sometimes
be matched to other published work. No claim of untraceable authorship is made.

## Before sharing changes

Check the staged diff and commit metadata for personal names, email addresses,
local paths, access tokens, private links, copied discussion text and retrieved
abstracts. Keep real credentials and harvested output outside tracked files.
The automated release scan catches common patterns; it cannot establish anonymity
against every possible external source.
