# Sources and credits

The workflow combines publisher-deposited Crossref records with DOI-based OpenAlex
lookups and Semantic Scholar abstract lookups. Each provider contributes different
coverage. A missing field in one service is not evidence that the article lacks an
abstract, and a populated field is not proof that it contains the correct abstract.

| Source | Role | Documentation |
|---|---|---|
| Crossref and its member publishers | Journal/ISSN inventory, DOI metadata, deposited abstracts and references | [REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [API documentation repository](https://github.com/CrossRef/rest-api-doc) |
| OpenAlex / OurResearch | DOI-based supplementary abstracts, work metadata and reference identifiers | [API reference](https://help.openalex.org/api/), [authentication](https://help.openalex.org/api/authentication/), [work data](https://help.openalex.org/data/works/) |
| Semantic Scholar / Allen Institute for AI | Batched DOI lookup for remaining abstract gaps | [Academic Graph API](https://api.semanticscholar.org/api-docs/), [platform](https://www.semanticscholar.org/product/api) |
| UT Dallas and the Financial Times | Journal-list membership, separately versioned from collection evidence | See [journal registry sources](JOURNALS.md) |

Method references: Priem, Piwowar and Orr (2022),
[OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts](https://arxiv.org/abs/2205.01833);
Kinney et al. (2023),
[The Semantic Scholar Open Data Platform](https://arxiv.org/abs/2301.10140).
Credit also belongs to the article authors, publishers and repository depositors
whose metadata these services aggregate. None endorses this toolkit.

The four collection stages were adapted from an earlier private research workflow
built with assistance from Claude Code and Codex. This release preserves its
source ordering, saved-response replay, explicit review decisions, and gap reporting.
It adds a portable command interface, a versioned registry, synthetic tests and
credential handling. Project-specific data and discussion histories are not included.

## Credentials and service limits

Checked against provider documentation on 23 October 2026. Limits can change.

- Crossref supports anonymous access and an optional contact address for its polite
  pool. `CROSSREF_MAILTO` is optional; if supplied it is sent to Crossref. See
  [access and authentication](https://www.crossref.org/documentation/retrieve-metadata/).
- OpenAlex supports keyless basic access and recommends an API key at scale. Set
  `OPENALEX_API_KEY` for your own key. Current documentation supports a bearer header;
  this avoids putting the key in request URLs. Keyless and authenticated requests have
  different budgets, and a 429 can mean a daily budget or a rate limit. See
  [authentication and limits](https://help.openalex.org/api/authentication/) and
  [pricing](https://help.openalex.org/access/pricing/).
- Set `SEMANTIC_SCHOLAR_API_KEY` if you have a Semantic Scholar key. The paper batch
  endpoint accepts at most 500 identifiers per call. See the
  [batch endpoint](https://api.semanticscholar.org/api-docs/snippets).

The tools read these variables from the process environment; they do not create
accounts, buy credits, or load `.env` files automatically. Use your own credentials.
Avoid putting credentials in command lines or shared logs. Raw data and local run
folders are ignored by Git, but still inspect anything you deliberately share.

## Code and retrieved content have different rights

The MIT license applies to this repository's code and documentation. It does not
grant rights to abstracts retrieved later. Crossref explicitly distinguishes
bibliographic metadata from abstracts, whose copyright remains with the publisher
or author. See [Crossref licensing](https://www.crossref.org/documentation/retrieve-metadata/#licensing).
Check applicable source terms and article licenses before redistributing retrieved
texts. This repository ships synthetic examples rather than an abstract corpus.
