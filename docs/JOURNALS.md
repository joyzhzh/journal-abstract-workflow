# Journal scope and identifiers

Snapshot: **23 October 2026**. The catalog contains **55 titles**: the current UTD24/FT50 union (51), three titles removed from FT50 in 2026, and Strategy Science as an optional out-of-list example. It is a catalog of business journals, not a claim that every title is a management journal or that all have been collected successfully.

The default selection is **19 journals in the current union with historical pipeline evidence**. The other two historical demonstrations are Organization Studies (FT50 before the 2026 revision) and Strategy Science (neither list). No accounting, finance, economics, marketing, operations, information-systems or psychology title is claimed to have been demonstrated merely because it appears on a ranking list. Some demonstrated titles are from those adjacent fields.

## Source verification

- **UTD24:** all 24 names were read from the search-indexed [official UT Dallas list](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals). Direct retrieval timed out. The site's “Journal on Computing” is cataloged as INFORMS Journal on Computing. Membership is separate from the ranking's date and article-type rules.
- **FT50, 2026 version:** the [official FT short URL](https://www.ft.com/ft50-journals) returned HTTP 404 during this check. The 50-title membership is corroborated by the [CEIBS institutional library list](https://ceibs.libguides.com/c.php?g=963339&p=7006421), dated 29 April 2026. This is institutional corroboration, not direct verification of the current FT article.
- **FT50, 2016 version:** the [official historical page](https://www.ft.com/content/3405a512-5cbb-11e1-8f1f-00144feabdc0) was paywalled. The [University of Hong Kong library transcription](https://libguides.lib.hku.hk/c.php?g=766106&p=6758018) was used to reconcile the historical column. The 2026 list adds Academy of Management Annals, American Sociological Review and Psychological Science, and removes Human Relations, Journal of Business Ethics and Organization Studies.
- **Identifiers:** Crossref's public `/journals/{ISSN}` metadata endpoint was queried on the snapshot date for the primary identifier of every catalog entry. It returned a matching journal title for 54 titles and supplied the listed additional identifiers. The original demonstration's extra identifiers were queried individually too. Harvard Business Review's ISSN is verified by the [ISSN International Centre](https://portal.issn.org/resource/issn/0017-8012), but its Crossref journal endpoint returned 404. The JSON keeps the source URL and result for each check.

`issns` contains query identifiers, which can include publisher aliases and predecessor titles. It is not asserted to be an exhaustive ISSN authority record. Two inherited Crossref query aliases fail the ISSN checksum: **1526-5489** (Manufacturing & Service Operations Management) and **1540-8520** (Entrepreneurship Theory and Practice). Their live Crossref endpoints returned the matching journals, so they remain explicitly annotated query aliases rather than being presented as canonical ISSNs. The JSON documents predecessor queries for Operations Research and Entrepreneurship Theory and Practice. New live deposits can change the number and contents of returned records.

## How to read the catalog

- **Demonstrated:** historical saved-source collection, screening, review and rebuild evidence exists. This repository distributes the reusable tools and aggregate account, not the private source responses or individual decisions. See [Evidence](EVIDENCE.md).
- **Snapshot only:** INFORMS Journal on Computing has historical Crossref collection evidence only; the complete enrichment and review pipeline was not demonstrated.
- **Configured only:** identifier and list membership are cataloged; journal-wide retrieval and content review have not been demonstrated.
- **Unsupported route:** the listed ISSN does not currently yield the Crossref journal endpoint needed to start this workflow. An explicit selection requires another enumeration route.

The `default` flag selects the 19 demonstrated current-list journals. `utd24`, `ft50_2016` and `ft50_2026` are independent membership flags. `retrieval_available` indicates whether the starting Crossref journal endpoint was available during the identifier check; it is not an abstract-coverage guarantee.

## Catalog

| Journal | UTD24 | FT50 2016 | FT50 2026 | Evidence | Default | Query ISSNs |
|---|:---:|:---:|:---:|---|:---:|---|
| Academy of Management Annals | — | — | yes | Demonstrated | yes | 1941-6520, 1941-6067 |
| Academy of Management Journal | yes | yes | yes | Demonstrated | yes | 0001-4273, 1948-0989 |
| Academy of Management Review | yes | yes | yes | Demonstrated | yes | 0363-7425, 1930-3807 |
| Accounting, Organizations and Society | — | yes | yes | Configured only | — | 0361-3682 |
| Administrative Science Quarterly | yes | yes | yes | Demonstrated | yes | 0001-8392, 1930-3815 |
| American Economic Review | — | yes | yes | Configured only | — | 0002-8282, 1944-7981 |
| American Sociological Review | — | — | yes | Demonstrated | yes | 0003-1224, 1939-8271 |
| Contemporary Accounting Research | — | yes | yes | Configured only | — | 0823-9150, 1911-3846 |
| Econometrica | — | yes | yes | Configured only | — | 0012-9682, 1468-0262 |
| Entrepreneurship Theory and Practice | — | yes | yes | Demonstrated | yes | 1042-2587, 1540-8520, 1540-6520, 0363-9428 |
| Harvard Business Review | — | yes | yes | Unsupported route | — | 0017-8012 |
| Human Relations | — | yes | — | Configured only | — | 0018-7267, 1741-282X |
| Human Resource Management | — | yes | yes | Configured only | — | 0090-4848, 1099-050X |
| Information Systems Research | yes | yes | yes | Demonstrated | yes | 1047-7047, 1526-5536 |
| INFORMS Journal on Computing | yes | — | — | Snapshot only | — | 1091-9856, 1526-5528, 0899-1499, 2326-3245 |
| Journal of Accounting and Economics | yes | yes | yes | Configured only | — | 0165-4101 |
| Journal of Accounting Research | yes | yes | yes | Configured only | — | 0021-8456, 1475-679X |
| Journal of Applied Psychology | — | yes | yes | Configured only | — | 0021-9010, 1939-1854 |
| Journal of Business Ethics | — | yes | — | Configured only | — | 0167-4544, 1573-0697 |
| Journal of Business Venturing | — | yes | yes | Demonstrated | yes | 0883-9026 |
| Journal of Consumer Psychology | — | yes | yes | Configured only | — | 1057-7408, 1532-7663 |
| Journal of Consumer Research | yes | yes | yes | Configured only | — | 0093-5301, 1537-5277 |
| Journal of Finance | yes | yes | yes | Configured only | — | 0022-1082, 1540-6261 |
| Journal of Financial and Quantitative Analysis | — | yes | yes | Configured only | — | 0022-1090, 1756-6916 |
| Journal of Financial Economics | yes | yes | yes | Configured only | — | 0304-405X |
| Journal of International Business Studies | yes | yes | yes | Demonstrated | yes | 0047-2506, 1478-6990, 0047-8210 |
| Journal of Management | — | yes | yes | Demonstrated | yes | 0149-2063, 1557-1211 |
| Journal of Management Information Systems | — | yes | yes | Configured only | — | 0742-1222, 1557-928X |
| Journal of Management Studies | — | yes | yes | Demonstrated | yes | 0022-2380, 1467-6486 |
| Journal of Marketing | yes | yes | yes | Configured only | — | 0022-2429, 1547-7185 |
| Journal of Marketing Research | yes | yes | yes | Configured only | — | 0022-2437, 1547-7193 |
| Journal of Operations Management | yes | yes | yes | Configured only | — | 0272-6963, 1873-1317 |
| Journal of Political Economy | — | yes | yes | Configured only | — | 0022-3808, 1537-534X |
| Journal of the Academy of Marketing Science | — | yes | yes | Configured only | — | 0092-0703, 1552-7824 |
| Management Science | yes | yes | yes | Demonstrated | yes | 0025-1909, 1526-5501 |
| Manufacturing & Service Operations Management | yes | yes | yes | Demonstrated | yes | 1523-4614, 1526-5498, 1526-5489 |
| Marketing Science | yes | yes | yes | Demonstrated | yes | 0732-2399, 1526-548X |
| MIS Quarterly | yes | yes | yes | Configured only | — | 0276-7783, 2162-9730 |
| MIT Sloan Management Review | — | yes | yes | Configured only | — | 1532-8937, 1532-9194 |
| Operations Research | yes | yes | yes | Demonstrated | yes | 0030-364X, 1526-5463, 0096-3984 |
| Organization Science | yes | yes | yes | Demonstrated | yes | 1047-7039, 1526-5455 |
| Organization Studies | — | yes | — | Demonstrated | — | 0170-8406, 1741-3044 |
| Organizational Behavior and Human Decision Processes | — | yes | yes | Configured only | — | 0749-5978, 1095-9920 |
| Production and Operations Management | yes | yes | yes | Configured only | — | 1059-1478, 1937-5956 |
| Psychological Science | — | — | yes | Configured only | — | 0956-7976, 1467-9280 |
| Quarterly Journal of Economics | — | yes | yes | Configured only | — | 0033-5533, 1531-4650 |
| Research Policy | — | yes | yes | Demonstrated | yes | 0048-7333 |
| Review of Accounting Studies | — | yes | yes | Configured only | — | 1380-6653, 1573-7136 |
| Review of Economic Studies | — | yes | yes | Configured only | — | 0034-6527, 1467-937X |
| Review of Finance | — | yes | yes | Configured only | — | 1572-3097, 1573-692X, 1875-824X |
| Review of Financial Studies | yes | yes | yes | Configured only | — | 0893-9454, 1465-7368 |
| Strategic Entrepreneurship Journal | — | yes | yes | Demonstrated | yes | 1932-4391, 1932-443X |
| Strategic Management Journal | yes | yes | yes | Demonstrated | yes | 0143-2095, 1097-0266 |
| Strategy Science | — | — | — | Demonstrated | — | 2333-2050, 2333-2077 |
| The Accounting Review | yes | yes | yes | Configured only | — | 0001-4826, 1558-7967 |

Full machine-readable registry: [`config/journals.json`](../config/journals.json). List membership is descriptive and implies no endorsement by UT Dallas, the Financial Times, publishers or data services.
