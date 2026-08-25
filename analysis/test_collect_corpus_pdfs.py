#!/usr/bin/env python3
"""Deterministic checks for `analysis/collect_corpus_pdfs.py`.

Runs standalone, with no test runner:

    python analysis/test_collect_corpus_pdfs.py

Every fixture is synthetic and written to a fresh temp dir. Nothing under
`postanalysis/` is read or written, and no test opens a socket.
"""
from __future__ import annotations
import csv, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "collect_corpus_pdfs.py"
WATCH = HERE / "watch_progress.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = load("collect_corpus_pdfs", SCRIPT)
W = load("watch_progress", WATCH)

CORPUS_COLS = ["work_id", "canonical_paper_id", "source_group", "decision", "year", "venue", "title", "doi"]
VERSION_COLS = ["work_id", "canonical_paper_id", "paper_id", "doi", "pmid", "arxiv_id"]


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return path


def run_script(td: Path, *, extra=(), corpus=None, versions=None) -> subprocess.CompletedProcess:
    src = td / "corpus.csv"
    ver = td / "versions.csv"
    out = td / "pdfs"
    write_csv(src, corpus or [], CORPUS_COLS)
    write_csv(ver, versions or [], VERSION_COLS)
    meta = td / "works_meta.csv"
    write_csv(meta, [], ["work_id", "canonical_paper_id", "title", "doi", "authors", "year", "venue"])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus-csv", str(src), "--versions-csv", str(ver),
         "--works-csv", str(meta), "--out", str(out),
         "--sleep", "0", "--arxiv-sleep", "0", *extra],
        capture_output=True, text=True,
    )
    return proc


class FakeFetcher(P.Fetcher):
    def __init__(self, json_by_url=None, bytes_by_url=None, **kw):
        super().__init__(sleep=0, arxiv_sleep=0, **kw)
        self.json_by_url = json_by_url or {}
        self.bytes_by_url = bytes_by_url or {}
        self.json_calls: list[str] = []
        self.byte_calls: list[str] = []

    def get_json(self, url: str):
        self.json_calls.append(url)
        if url in self.json_by_url:
            return self.json_by_url[url]
        for k, v in self.json_by_url.items():
            if k and k in url:
                return v
        if "unpaywall.org" in url:
            return {"best_oa_location": None, "oa_locations": []}
        if "openalex.org/works?" in url:
            return {"results": []}
        if "openalex.org/works/" in url:
            return {"best_oa_location": None, "primary_location": None, "open_access": {}, "locations": []}
        if "api.crossref.org" in url:
            return {"message": {"items": [], "link": [], "title": [], "DOI": ""}}
        if "europepmc" in url:
            return {"resultList": {"result": []}}
        if "ncbi.nlm.nih.gov" in url:
            return {"records": [], "linksets": [], "esearchresult": {"idlist": []}}
        raise KeyError(url)

    def get_bytes(self, url: str):
        self.byte_calls.append(url)
        if url not in self.bytes_by_url:
            raise KeyError(url)
        return self.bytes_by_url[url]


def test_filename_stems_prefer_doi():
    assert P.file_stem("10.1038/s41586-026-10735-w", "2301.0001", "123", "work_x") == "doi_10.1038_s41586-026-10735-w"
    assert P.file_stem("", "1405.1965", "123", "work_x") == "arxiv_1405.1965"
    assert P.file_stem("", "", "26134359", "work_x") == "pmid_26134359"
    assert P.file_stem("", "", "", "work_325cae202b91894a") == "work_325cae202b91894a"
    assert P.norm_doi("https://doi.org/10.1101/ABC") == "10.1101/abc"
    assert P.norm_pmid("11301197.0") == "11301197"
    assert P.norm_arxiv("arXiv:1405.1965v2") == "1405.1965"
    assert P.arxiv_from_doi("10.48550/arxiv.2301.01234") == "2301.01234"


def test_landing_urls_and_arxiv_pdf():
    work = {"work_id": "work_a", "canonical_paper_id": "abc123", "doi": "https://doi.org/10.1038/s41586-020-0001", "title": "A"}
    versions = [{"doi": "", "pmid": "12345.0", "arxiv_id": "2001.00001"}]
    ids = P.identifiers_for(work, versions)
    assert ids["doi"] == "10.1038/s41586-020-0001"
    assert ids["pmid"] == "12345"
    assert ids["arxiv_id"] == "2001.00001"
    assert ids["landing_url"] == "https://doi.org/10.1038/s41586-020-0001"
    assert ids["doi_url"] == ids["landing_url"]
    assert ids["pmid_url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert ids["arxiv_abs_url"] == "https://arxiv.org/abs/2001.00001"
    assert ids["semantic_scholar_url"] == "https://www.semanticscholar.org/paper/abc123"
    assert ids["stem"] == "doi_10.1038_s41586-020-0001"
    seed_ids = P.identifiers_for(
        {"work_id": "work_seed", "doi": "10.1038/nature12346", "pmid": "23925239", "arxiv_id": ""},
        [],
    )
    assert seed_ids["pmid"] == "23925239"
    assert seed_ids["pmid_url"] == "https://pubmed.ncbi.nlm.nih.gov/23925239/"
    assert P.direct_pdf_candidates(ids) == [("https://arxiv.org/pdf/2001.00001.pdf", "arxiv")]
    bio = P.direct_pdf_candidates({"doi": "10.1101/2020.01.01.123", "venue": "bioRxiv", "arxiv_id": ""})
    assert bio == [("https://www.biorxiv.org/content/10.1101/2020.01.01.123.full.pdf", "biorxiv")]
    assert P.looks_like_pdf_url("https://cdn.example/paper.pdf")
    assert P.looks_like_pdf_url("https://advanced.onlinelibrary.wiley.com/doi/pdfdirect/10.1002/advs.202511922?download=true")
    assert not P.looks_like_pdf_url("https://advanced.onlinelibrary.wiley.com/doi/epdf/10.1002/advs.202511922")
    assert not P.looks_like_pdf_url("https://doi.org/10.1038/s41586-026-10735-w")
    assert P.wiley_epdf_url("10.1002/advs.202511922") == (
        "https://advanced.onlinelibrary.wiley.com/doi/epdf/10.1002/advs.202511922"
    )
    assert P.wiley_pdfdirect_url("10.1002/advs.202511922") == (
        "https://advanced.onlinelibrary.wiley.com/doi/pdfdirect/10.1002/advs.202511922?download=true"
    )
    assert P.wiley_epdf_url("10.1002/alz.069442").startswith("https://alz-journals.onlinelibrary.wiley.com/doi/epdf/")
    assert P.wiley_epdf_url("10.1111/cgf.14574").startswith("https://onlinelibrary.wiley.com/doi/epdf/")
    assert P.wiley_epdf_url("10.1096/fasebj.30.1_supplement.1006.6").startswith("https://faseb.onlinelibrary.wiley.com/")
    assert P.wiley_epdf_url("10.1038/s41586-019-1352-7") == ""
    assert P.pmc_pdf_url("https://pmc.ncbi.nlm.nih.gov/articles/PMC13174447/") == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13174447/pdf/"
    assert P.pmcid_from_text("https://europepmc.org/articles/PMC4844839?pdf=render") == "PMC4844839"
    assert P.pmcid_from_text("see PMC3095821 in the record") == "PMC3095821"
    html = '''
      <a href="pdf/nihms757168.pdf">PDF (2.1 MB)</a>
      <a href="/articles/instance/4844839/bin/NIHMS757168-supplement-2.pdf">supp</a>
    '''
    urls = P.pmc_named_pdf_urls_from_html(html, "PMC4844839")
    assert urls == ["https://pmc.ncbi.nlm.nih.gov/articles/PMC4844839/pdf/nihms757168.pdf"]


def test_semantic_scholar_fallback_when_no_ids():
    ids = P.identifiers_for({"work_id": "work_z", "canonical_paper_id": "deadbeef", "doi": "", "title": "TrakEM"}, [])
    assert ids["doi"] == ids["pmid"] == ids["arxiv_id"] == ""
    assert ids["landing_url"] == "https://www.semanticscholar.org/paper/deadbeef"
    assert ids["stem"] == "work_z"


def test_pdf_magic_rejects_html():
    assert P.looks_like_pdf(b"%PDF-1.4\n...")
    assert P.looks_like_html(b"<!DOCTYPE html><html>")
    assert not P.looks_like_pdf(b"<!DOCTYPE html><html>")


def test_unpaywall_and_openalex_candidate_parsing():
    up = P.unpaywall_candidates({
        "best_oa_location": {"url_for_pdf": "", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1"},
        "oa_locations": [{"url": "https://doi.org/10.1/x"}],
    })
    assert up == [("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1/pdf/", "unpaywall")]
    up2 = P.unpaywall_candidates({"best_oa_location": {"url_for_pdf": "https://oa.example/a.pdf", "url": "https://oa.example/a"}})
    assert up2 == [("https://oa.example/a.pdf", "unpaywall")]
    oa = P.openalex_candidates({"best_oa_location": {"pdf_url": "https://oa.example/b.pdf"}, "open_access": {"oa_url": "https://oa.example/b.pdf"}})
    assert oa == [("https://oa.example/b.pdf", "openalex")]
    pmc = P.europepmc_candidates({"resultList": {"result": [{"pmcid": "PMC1", "fullTextUrlList": {"fullTextUrl": [{"documentStyle": "pdf", "url": "https://epmc.example/x.pdf"}]}}]}})
    assert pmc[0][1] == "pmc"
    assert pmc[1] == ("https://epmc.example/x.pdf", "europepmc")


def test_local_ids_catalog_and_refuse_input_dir():
    td = Path(tempfile.mkdtemp())
    corpus = [
        {"work_id": "work_b", "canonical_paper_id": "p2", "source_group": "core_audit", "decision": "core_relevant",
         "year": "2020", "venue": "arXiv.org", "title": "No DOI arxiv", "doi": ""},
        {"work_id": "work_a", "canonical_paper_id": "p1", "source_group": "core_audit", "decision": "core_relevant",
         "year": "2021", "venue": "Nature", "title": "Has DOI", "doi": "10.1038/s41586-021-1"},
        {"work_id": "work_c", "canonical_paper_id": "p3", "source_group": "role_bridge", "decision": "role_bridge",
         "year": "2016", "venue": "", "title": "Software note", "doi": ""},
    ]
    versions = [
        {"work_id": "work_a", "canonical_paper_id": "p1", "paper_id": "p1", "doi": "10.1038/s41586-021-1", "pmid": "111.0", "arxiv_id": ""},
        {"work_id": "work_b", "canonical_paper_id": "p2", "paper_id": "p2", "doi": "", "pmid": "", "arxiv_id": "2001.00001"},
        {"work_id": "work_c", "canonical_paper_id": "p3", "paper_id": "p3", "doi": "", "pmid": "", "arxiv_id": ""},
    ]
    proc = run_script(td, extra=("--local-ids-only", "--resolve-only"), corpus=corpus, versions=versions)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    out = td / "pdfs"
    rows = list(csv.DictReader((out / "paper_links.csv").open(encoding="utf-8")))
    assert [r["work_id"] for r in rows] == ["work_a", "work_b", "work_c"]
    by = {r["work_id"]: r for r in rows}
    assert by["work_a"]["stem"] == "doi_10.1038_s41586-021-1"
    assert by["work_a"]["landing_url"] == "https://doi.org/10.1038/s41586-021-1"
    assert by["work_a"]["pdf_status"] == "linked"
    assert by["work_b"]["stem"] == "arxiv_2001.00001"
    assert by["work_b"]["pdf_url"] == "https://arxiv.org/pdf/2001.00001.pdf"
    assert by["work_b"]["pdf_status"] == "oa_resolved"
    assert by["work_c"]["landing_url"] == "https://www.semanticscholar.org/paper/p3"
    assert by["work_c"]["pdf_status"] == "linked"
    assert not list((out / "files").glob("*.pdf"))
    summary = json.loads((out / "pdf_summary.json").read_text())
    assert summary["corpus_works"] == 3
    assert summary["with_landing_url"] == 3
    assert summary["with_pdf_url"] == 1

    proc2 = run_script(td, extra=("--local-ids-only", "--resolve-only", "--limit", "1"), corpus=corpus, versions=versions)
    assert proc2.returncode == 0, proc2.stderr + proc2.stdout
    rows2 = list(csv.DictReader((out / "paper_links.csv").open(encoding="utf-8")))
    assert len(rows2) == 3

    src = td / "corpus.csv"
    bad = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus-csv", str(src), "--versions-csv", str(td / "versions.csv"),
         "--out", str(src.parent), "--local-ids-only", "--resolve-only", "--sleep", "0"],
        capture_output=True, text=True,
    )
    assert bad.returncode != 0
    assert "refusing to write into an input directory" in bad.stderr + bad.stdout


def test_union_corpora_fills_doi_from_works_csv():
    td = Path(tempfile.mkdtemp())
    a = [
        {"work_id": "work_a", "canonical_paper_id": "", "source_group": "core_audit", "decision": "core_relevant",
         "year": "2020", "venue": "", "title": "Paper A", "doi": ""},
    ]
    b = [
        {"work_id": "work_a", "canonical_paper_id": "", "source_group": "", "decision": "adjacent_relevant",
         "year": "2020", "venue": "Nature", "title": "Paper A", "doi": ""},
        {"work_id": "work_d", "canonical_paper_id": "", "source_group": "", "decision": "core_relevant",
         "year": "2021", "venue": "eLife", "title": "Paper D", "doi": ""},
    ]
    pa = write_csv(td / "a.csv", a, CORPUS_COLS)
    pb = write_csv(td / "b.csv", b, CORPUS_COLS)
    meta = write_csv(td / "meta.csv", [
        {"work_id": "work_d", "canonical_paper_id": "pD", "title": "Paper D", "doi": "10.7554/elife.1",
         "authors": "A", "year": "2021", "venue": "eLife"},
    ], ["work_id", "canonical_paper_id", "title", "doi", "authors", "year", "venue"])
    rows = P.union_corpus_rows([pa, pb], meta)
    assert [r["work_id"] for r in rows] == ["work_a", "work_d"]
    assert rows[1]["doi"] == "10.7554/elife.1"
    assert rows[1]["canonical_paper_id"] == "pD"
    assert rows[0]["decision"] == "core_relevant"


def test_download_writes_pdf_and_skips_existing():
    td = Path(tempfile.mkdtemp())
    work = {
        "work_id": "work_a", "canonical_paper_id": "p1", "source_group": "core_audit", "decision": "core_relevant",
        "year": "2021", "venue": "Nature", "title": "Has DOI", "doi": "10.1038/demo", "pmid": "", "arxiv_id": "",
        "landing_url": "https://doi.org/10.1038/demo", "doi_url": "https://doi.org/10.1038/demo",
        "pmid_url": "", "arxiv_abs_url": "", "semantic_scholar_url": "https://www.semanticscholar.org/paper/p1",
        "stem": "doi_10.1038_demo",
    }
    dest = td / "files" / "doi_10.1038_demo.pdf"
    pdf = b"%PDF-1.4\nfixture\n"
    html = b"<!DOCTYPE html><html>paywall</html>"
    fetcher = FakeFetcher(
        email="dev@example.org",
        json_by_url={
            "https://api.unpaywall.org/v2/10.1038/demo?email=dev%40example.org": {
                "best_oa_location": {"url_for_pdf": "https://cdn.example/paper.pdf"},
            }
        },
        bytes_by_url={"https://cdn.example/paper.pdf": pdf, "https://cdn.example/html": html},
    )
    rec = P.process_work(work, dest, fetcher, None, local_ids_only=False, resolve_only=False, force=False, skip_attempted=False)
    assert rec["pdf_status"] == "downloaded"
    assert dest.read_bytes() == pdf
    assert rec["sha256"] == P.sha256_bytes(pdf)
    assert rec["pdf_source"] == "unpaywall"
    assert "decision" not in rec

    rec2 = P.process_work(work, dest, fetcher, rec, local_ids_only=False, resolve_only=False, force=False, skip_attempted=False)
    assert rec2["pdf_status"] == "downloaded"
    assert rec2["attempts"] == ["resume:existing_file"]
    assert fetcher.byte_calls == ["https://cdn.example/paper.pdf"]


def test_html_payload_is_not_saved_as_pdf():
    td = Path(tempfile.mkdtemp())
    work = {
        "work_id": "work_a", "canonical_paper_id": "p1", "title": "X", "doi": "10.1/x",
        "pmid": "", "arxiv_id": "", "landing_url": "https://doi.org/10.1/x",
        "doi_url": "https://doi.org/10.1/x", "pmid_url": "", "arxiv_abs_url": "",
        "semantic_scholar_url": "", "stem": "doi_10.1_x",
    }
    dest = td / "doi_10.1_x.pdf"
    fetcher = FakeFetcher(
        email="dev@example.org",
        json_by_url={"https://api.unpaywall.org/v2/10.1/x?email=dev%40example.org": {"best_oa_location": {"url_for_pdf": "https://cdn.example/html"}}},
        bytes_by_url={"https://cdn.example/html": b"<!DOCTYPE html><html>nope</html>"},
    )
    rec = P.process_work(work, dest, fetcher, None, local_ids_only=False, resolve_only=False, force=False, skip_attempted=False)
    assert rec["pdf_status"] == "download_failed"
    assert rec.get("pdf_source") != "direct_search"
    assert "not_pdf" in "|".join(rec["attempts"])
    assert not dest.exists()


def test_malformed_progress_last_record_wins():
    td = Path(tempfile.mkdtemp())
    path = td / "pdf_progress.jsonl"
    path.write_text("\n".join([
        json.dumps({"work_id": "w", "pdf_status": "paywall"}),
        "not json at all",
        json.dumps({"work_id": "w", "pdf_status": "downloaded", "pdf_url": "https://x"}),
    ]) + "\n")
    assert P.read_progress(path)["w"]["pdf_status"] == "downloaded"


def test_watch_progress_classifies_pdf_stream():
    rec = {"index": 1, "total": 3, "work_id": "work_a", "title": "A paper", "pdf_status": "downloaded",
           "stem": "doi_10.1_x", "pdf_source": "arxiv", "attempts": ["direct:arxiv", "download:arxiv:ok"]}
    assert W.kind_of(rec) == "pdf"
    line = W.fmt(rec)
    assert "downloaded" in line and "work_a" in line
    summary = W.summarize([rec, dict(rec, work_id="work_b", pdf_status="paywall", pdf_source="")])
    assert "downloaded=1" in summary and "paywall=1" in summary
    llm = {"index": 1, "total": 1, "work_id": "w1", "decision": "core_relevant", "confidence": 0.9, "roles": [], "noise_flags": []}
    assert W.kind_of(llm) == "llm"


def test_title_doi_match_rules():
    work = {"title": "Dense reconstruction of a cortical volume", "doi": "10.1038/s41586-020-0001", "year": "2020"}
    doi_hit = P.score_match(work, "Something else entirely", "10.1038/s41586-020-0001", 2011)
    assert doi_hit and doi_hit["match_method"] == "doi" and doi_hit["search_match"] is True
    title_hit = P.score_match(work, "Dense reconstruction of a cortical volume", "10.1101/not-the-same", 2020)
    assert title_hit and title_hit["match_method"] == "title" and title_hit["title_similarity"] >= P.TITLE_SIM_FLOOR
    assert P.score_match(work, "Unrelated graph theory of soap films", "10.9/zzz", 2020) is None


def test_direct_search_is_flagged_for_audit():
    td = Path(tempfile.mkdtemp())
    work = {
        "work_id": "work_s", "canonical_paper_id": "p9", "title": "A cortical connectome at synapse resolution",
        "doi": "10.1038/missing-oa", "pmid": "", "arxiv_id": "", "year": "2021", "venue": "Nature",
        "landing_url": "https://doi.org/10.1038/missing-oa", "doi_url": "https://doi.org/10.1038/missing-oa",
        "pmid_url": "", "arxiv_abs_url": "", "semantic_scholar_url": "", "stem": "doi_10.1038_missing-oa",
    }
    dest = td / "doi_10.1038_missing-oa.pdf"
    pdf = b"%PDF-1.4\nsearch-hit\n"
    oa_url = P.openalex_search_url(work["title"], "dev@example.org")
    fetcher = FakeFetcher(
        email="dev@example.org",
        json_by_url={
            oa_url: {"results": [{
                "display_name": "A cortical connectome at synapse resolution",
                "doi": "https://doi.org/10.1038/missing-oa",
                "publication_year": 2021,
                "best_oa_location": {"pdf_url": "https://cdn.example/search.pdf"},
            }]},
        },
        bytes_by_url={"https://cdn.example/search.pdf": pdf},
    )
    rec = P.process_work(work, dest, fetcher, None, local_ids_only=False, resolve_only=False,
                         force=False, skip_attempted=False, search_unresolved=True)
    assert rec["pdf_status"] == "downloaded"
    assert rec["pdf_source"] == "direct_search"
    assert rec["search_match"] is True
    assert rec["match_method"] == "doi"
    assert rec["matched_doi"] == "10.1038/missing-oa"
    assert dest.read_bytes() == pdf
    n = P.write_audit(td / "direct_search_audit.csv", [work], {"work_s": rec})
    assert n == 1
    rows = list(csv.DictReader((td / "direct_search_audit.csv").open(encoding="utf-8")))
    assert rows[0]["match_method"] == "doi" and rows[0]["search_api"] == "openalex"


def test_pubmed_idconv_elink_and_pmc_download():
    assert P.norm_pmcid("3531190") == "PMC3531190"
    assert P.norm_pmcid("PMC3531190") == "PMC3531190"
    pmcids, pmids = P.pmcids_from_idconv({"records": [{"pmcid": "PMC1", "pmid": "99", "doi": "10.1/x"}]})
    assert pmcids == ["PMC1"] and pmids == ["99"]
    assert P.pmcids_from_idconv({"records": [{"status": "error", "pmcid": "PMC1"}]}) == ([], [])
    assert P.pmcids_from_elink({"linksets": [{"linksetdbs": [{"dbto": "pmc", "linkname": "pubmed_pmc", "links": ["3531190"]}]}]}) == ["PMC3531190"]
    assert P.pmcids_from_elink({"linksets": [{"linksetdbs": [
        {"dbto": "pmc", "linkname": "pubmed_pmc_refs", "links": ["99999999"]},
        {"dbto": "pmc", "linkname": "pubmed_pmc", "links": ["3531190"]},
    ]}]}) == ["PMC3531190"]
    assert P.pmcids_from_elink({"linksets": [{"linksetdbs": [{"dbto": "pmc", "linkname": "pubmed_pmc_refs", "links": ["999"]}]}]}) == []
    cands = P.pubmed_cands_from_pmcids(["PMC1"])
    assert all(src == "pubmed" for _, src in cands)
    assert cands[0][0].startswith("https://europepmc.org/articles/PMC1")
    assert any(u.endswith("/PMC1/pdf/") for u, _ in cands)

    td = Path(tempfile.mkdtemp())
    work = {
        "work_id": "work_p", "canonical_paper_id": "p1", "title": "A PubMed paper",
        "doi": "10.1038/pubmed-demo", "pmid": "", "arxiv_id": "", "year": "2020",
        "landing_url": "https://doi.org/10.1038/pubmed-demo",
        "doi_url": "https://doi.org/10.1038/pubmed-demo",
        "pmid_url": "", "arxiv_abs_url": "", "semantic_scholar_url": "",
        "stem": "doi_10.1038_pubmed-demo",
    }
    dest = td / "doi_10.1038_pubmed-demo.pdf"
    pdf = b"%PDF-1.4\npmc\n"
    idconv = P.pubmed_idconv_url(["10.1038/pubmed-demo"], "dev@example.org")
    fetcher = FakeFetcher(
        email="dev@example.org",
        json_by_url={
            idconv: {"records": [{"pmcid": "PMC9", "pmid": "123", "doi": "10.1038/pubmed-demo"}]},
        },
        bytes_by_url={"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9/pdf/": pdf},
    )
    rec = P.process_work(
        work, dest, fetcher, {"pdf_status": "download_failed", "pdf_source": "unpaywall"},
        local_ids_only=False, resolve_only=False, force=False, skip_attempted=False,
        pubmed_only=True,
    )
    assert rec["pdf_status"] == "downloaded"
    assert rec["pdf_source"] == "pubmed"
    assert dest.read_bytes() == pdf
    assert not any("unpaywall.org" in u for u in fetcher.json_calls)

    miss = FakeFetcher(email="dev@example.org")
    dest2 = td / "missing.pdf"
    rec2 = P.process_work(
        work, dest2, miss, {"pdf_status": "search_matched", "pdf_source": "direct_search", "match_method": "doi"},
        local_ids_only=False, resolve_only=False, force=False, skip_attempted=False,
        pubmed_only=True,
    )
    assert rec2["pdf_status"] == "search_matched"
    assert rec2["pdf_source"] == "direct_search"
    assert rec2["match_method"] == "doi"
    assert not dest2.exists()


def test_manual_match_ignores_bibliography_dois_and_cvprw_filenames():
    cited = {
        "work_id": "work_cite", "title": "Sparse Scanning Electron Microscopy",
        "doi": "10.1017/s1431927620001361", "year": "2020",
    }
    real = {
        "work_id": "work_cag",
        "title": "Deep learning for brain electron microscopy segmentation: Advances, challenges, and future directions in connectomics and ultrastructure analysis",
        "doi": "10.1016/j.cag.2025.104391", "year": "2025",
    }
    mixed = ["10.1017/s1431927620001361", "10.1016/j.cag.2025.104391"]
    work, method = P.work_for_extracted_dois(mixed, [cited, real])
    assert work is None and method == ""
    work, method = P.work_for_extracted_dois(["10.1016/j.cag.2025.104391"], [cited, real])
    assert work["work_id"] == "work_cag" and method == "pdf_doi"

    sloppy = {
        "title": "Learning to Correct Sloppy Annotations in Electron Microscopy Volumes",
        "year": "2023",
    }
    guess, year = P.filename_title_guess(
        "Chen_Learning_To_Correct_Sloppy_Annotations_in_Electron_Microscopy_Volumes_CVPRW_2023_paper"
    )
    assert year == "2023"
    assert P.title_filename_hit(sloppy, guess, year)


def test_manual_ingest_matches_copies_and_logs():
    td = Path(tempfile.mkdtemp())
    corpus = [
        {"work_id": "work_veminr", "canonical_paper_id": "p1", "source_group": "role_bridge",
         "decision": "adjacent_relevant", "year": "2026", "venue": "Advanced Science",
         "title": "vEMINR: Ultra-Fast Isotropic Reconstruction for Volume Electron Microscopy With Implicit Neural Representation",
         "doi": "10.1002/advs.202511922"},
        {"work_id": "work_photonics66", "canonical_paper_id": "p2", "source_group": "core_audit",
         "decision": "role_bridge", "year": "2019", "venue": "Photonics",
         "title": "A Review of Intrinsic Optical Imaging Serial Blockface Histology (ICI-SBH) for Whole Rodent Brain Imaging",
         "doi": "10.3390/photonics6020066"},
        {"work_id": "work_photonics98", "canonical_paper_id": "p3", "source_group": "core_audit",
         "decision": "adjacent_relevant", "year": "2019", "venue": "Photonics",
         "title": "Optical Imaging in Brainsmatics", "doi": "10.3390/photonics6030098"},
        {"work_id": "work_closed", "canonical_paper_id": "p4", "source_group": "core_audit",
         "decision": "core_relevant", "year": "2021", "venue": "Nature",
         "title": "Paywalled connectome paper", "doi": "10.1038/closed-demo"},
    ]
    versions = [{"work_id": r["work_id"], "canonical_paper_id": r["canonical_paper_id"],
                 "paper_id": r["canonical_paper_id"], "doi": r["doi"], "pmid": "", "arxiv_id": ""} for r in corpus]
    pdf = b"%PDF-1.4\nmanual-fixture\n"
    oa = td / "pdfs" / "manual_OA"
    closed = td / "pdfs" / "manual_closed"
    oa.mkdir(parents=True)
    closed.mkdir()
    wiley = oa / "Advanced Science - 2026 - Yang - vEMINR  Ultra-Fast Isotropic Reconstruction for Volume Electron Microscopy With Implicit.pdf"
    wiley.write_bytes(pdf)
    (oa / "photonics-06-00066.pdf").write_bytes(pdf)
    (oa / "publisher-embedded-doi.pdf").write_bytes(b"%PDF-1.4\ndoi:10.3390/photonics6030098\n")
    (oa / "unmatched-noise.pdf").write_bytes(pdf)
    (closed / "doi_10.1038_closed-demo.pdf").write_bytes(pdf)

    proc = run_script(td, extra=("--ingest-manual",), corpus=corpus, versions=versions)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "unmatched-noise.pdf: unmatched" in proc.stderr
    out = td / "pdfs"
    dest_v = out / "files" / "doi_10.1002_advs.202511922.pdf"
    dest_p = out / "files" / "doi_10.3390_photonics6020066.pdf"
    dest_c = out / "files" / "doi_10.1038_closed-demo.pdf"
    dest_other = out / "files" / "doi_10.3390_photonics6030098.pdf"
    assert dest_v.read_bytes() == pdf
    assert dest_p.read_bytes() == pdf
    assert dest_c.read_bytes() == pdf
    assert dest_other.read_bytes().startswith(b"%PDF-1.4")
    rows = {r["work_id"]: r for r in csv.DictReader((out / "paper_links.csv").open(encoding="utf-8"))}
    assert rows["work_veminr"]["pdf_status"] == "downloaded"
    assert rows["work_veminr"]["pdf_source"] == "manual_oa"
    assert rows["work_veminr"]["match_method"] == "title"
    assert rows["work_photonics66"]["pdf_source"] == "manual_oa"
    assert rows["work_photonics66"]["match_method"] == "mdpi_article"
    assert rows["work_closed"]["pdf_source"] == "manual_closed"
    assert rows["work_closed"]["match_method"] == "stem"
    assert rows["work_photonics98"]["pdf_status"] == "downloaded"
    assert rows["work_photonics98"]["pdf_source"] == "manual_oa"
    assert rows["work_photonics98"]["match_method"] == "pdf_doi"
    progress = P.read_progress(out / "pdf_progress.jsonl")
    assert progress["work_veminr"]["attempts"] == ["ingest:manual_oa:title:copied"]
    summary = json.loads((out / "pdf_summary.json").read_text())
    assert summary["manual_ingested"] == 4
    assert summary["manual_problems"] == 1
    assert summary["downloaded"] == 4

    proc2 = run_script(td, extra=("--ingest-manual",), corpus=corpus, versions=versions)
    assert proc2.returncode != 0
    lines = [json.loads(x) for x in (out / "pdf_progress.jsonl").read_text().splitlines() if x.strip()]
    ingested = [r for r in lines if str(r.get("pdf_source", "")).startswith("manual_")]
    assert len(ingested) == 4


def main() -> None:
    tests = [
        test_filename_stems_prefer_doi,
        test_landing_urls_and_arxiv_pdf,
        test_semantic_scholar_fallback_when_no_ids,
        test_pdf_magic_rejects_html,
        test_unpaywall_and_openalex_candidate_parsing,
        test_local_ids_catalog_and_refuse_input_dir,
        test_union_corpora_fills_doi_from_works_csv,
        test_download_writes_pdf_and_skips_existing,
        test_html_payload_is_not_saved_as_pdf,
        test_malformed_progress_last_record_wins,
        test_watch_progress_classifies_pdf_stream,
        test_title_doi_match_rules,
        test_manual_match_ignores_bibliography_dois_and_cvprw_filenames,
        test_direct_search_is_flagged_for_audit,
        test_pubmed_idconv_elink_and_pmc_download,
        test_manual_ingest_matches_copies_and_logs,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e!r}", file=sys.stderr)
            raise
    print(f"{len(tests) - failed}/{len(tests)} passed")


if __name__ == "__main__":
    main()
