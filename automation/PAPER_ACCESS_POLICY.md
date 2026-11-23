# Autonomous full-text access

Effective 13 November 2026, following the owner's request to eliminate routine paper-download approval. Read this with the active runbook. This changes paper acquisition only: all science, media-rights, review, publishing and account safeguards remain active.

## Authorization and source selection

Routine discovery, reading and lawful retrieval of public open-access research papers for Toxic Tales are already owner-authorized. Do not ask the owner to approve individual paper downloads or an arbitrary batch of twenty. Do not purchase access, use institutional credentials or depend on the owner's computer.

PubMed is an index, not a guarantee of full text. For newly selected primary studies, require a verified PMCID and an accessible complete article in the PMC/Europe PMC open-access subset. Prefer full HTML or structured JATS XML; a PDF download is not necessary. Preserve the already reviewed and scheduled TT-007 bumblebee paper and all released sources, even when their existing full text came from another legitimate open source.

Screen at least six unused candidates as before. Use current DOI/PMCID metadata, relevance and potential story quality to shortlist; then retrieve the selected papers through the supported route below. Keep a small reserve of accessible candidates when practical. Cached papers are candidates, not a promised publication order, and no fixed next-twenty queue exists. Downloading twenty papers is not necessary to authorize future work.

## Supported cloud retrieval

Use the existing connected GitHub repository and standard free public GitHub Actions. The additive workflow .github/workflows/fetch-open-papers.yml runs automation/fetch_open_papers.py. It has no posting capability and no independent recurring schedule.

1. Verify each PMCID and expected DOI using original metadata. Read current automation/paper-retrieval-request.json/report and any in-progress retrieval run before replacing a request. Reuse an identical completed result or wait for an in-progress matching request. Coordinate this work under the current production claim.
2. Commit automation/paper-retrieval-request.json using expected-head compare-and-swap, with exact keys repository, request_id and papers. repository is akshaymohan16/toxic-tales-library; request_id is a unique safe identifier; papers contains one to twenty unique objects with pmcid and expected_doi. Do not supply arbitrary download URLs.
3. The workflow retrieves full-text JATS through the official Europe PMC REST API, with the official PMC OAI-PMH API as a fallback. Sequential bounded requests and retries are required. It verifies article identity, nonempty body and an unambiguous article-level CC BY or CC0 licence before saving a public repository cache.
4. Inspect the actual workflow jobs and automation/paper-retrieval-report.json. Require the report request_sha256 to match the current request. Read research/fulltext/PMCID/metadata.json, article.txt and, where structure matters, article.xml through the GitHub connector. Check stored hashes. These files remain outside site/ and are not added as publisher PDFs to the public research website.
5. Read the complete selected paper, not merely the report or abstract. Inspect Methods, Results, Discussion, tables, figure captions and every supplement necessary to support planned claims. XML and text retrieval do not retrieve image binaries or guarantee complete supplements. The report is an access result, never an editorial approval or proof that the paper has been read.

The cache preserves source, licence, retrieval time and exact hashes. Recheck current publisher/PubMed/PMC notices and relevant contrary evidence when choosing a cached paper. A cached copy is a dated snapshot, not a fresh correction/retraction check. Do not alter released episode/evidence files to add these new access records.

## Failure handling and permissions

For a paywall, login, CAPTCHA, unavailable full text, unsuitable cache licence, incomplete main article or inaccessible essential supplement: record the reason and choose another eligible candidate without asking the owner to fetch or approve that paper. Preserve partial progress and successful cached records. A transient API outage may receive bounded retry and later normal recovery; never declare inaccessible evidence reviewed.

Do not automate a browser challenge, bypass an app approval or assume that open-access copyright status disables platform permission controls. If a tool explicitly requires connection or approval, respect that boundary. Continue independent work where possible; only a genuine owner-action blocker affecting the available authorized workflow needs an alert. The earlier download prompt's exact cause has not been established and must not be described as resolved by source choice alone.

Article text access does not authorize reuse of every figure, photo, soundtrack or supplementary video. Check each planned asset's licence and excluded third-party credits separately. Website records continue to link the paper and give evidence, limits and credits. No scientific, visual or exact-export quality gate is relaxed.

## Official service references checked 13 November 2026

- https://pmc.ncbi.nlm.nih.gov/tools/openftlist/
- https://pmc.ncbi.nlm.nih.gov/tools/oai/
- https://europepmc.org/RestfulWebService
- https://europepmc.org/downloads/openaccess

Use supported API services for programmatic retrieval; do not scrape batches from PMC article webpages. The legacy PMC OA Web Service was retired in August 2026 and must not be used.
