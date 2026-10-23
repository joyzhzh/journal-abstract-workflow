# Release privacy

This repository was prepared as a new Git history. It does not carry the private
source repository's commits, contributors, discussions, raw API responses,
article abstracts, local review ledgers, or machine paths.

Commit author and committer identities use the neutral project name and an address
under the reserved `example.invalid` domain. This address is not a contact channel.
Examples and test abstracts are synthetic. Personal credentials are read only from
environment variables. Local run folders are ignored by Git.

The API transport rejects malformed keys without echoing their values and refuses
redirects to a different host, port or scheme before sending another request.
It permits redirects within the same HTTPS origin. This protects configured
credentials from being forwarded to a different destination by a redirect.

The default `runs/` folder, private preparation notes and recovery files are ignored.
For a custom output directory, the runner creates a data/cache ignore file only if
no `.gitignore` exists there; check your own ignore rules before committing outputs.
Review notes and downloaded metadata can themselves contain identifying details.

GitHub ownership and repository activity are visible under the owning account
in this public repository. Anonymized contents and Git author fields do not
hide the repository owner, pusher, or platform activity. Aggregate journal coverage
is retained to explain the evidence and limitations; such statistics can sometimes
be matched to other published work. No claim of untraceable authorship is made.

## Before sharing changes

Check the staged diff and commit metadata for personal names, email addresses,
local paths, access tokens, private links, copied discussion text and retrieved
abstracts. Keep real credentials and harvested output outside tracked files.
The automated release scan catches common patterns; it cannot establish anonymity
against every possible external source.
