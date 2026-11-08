"""PubMed responses are parsed with defusedxml: entity tricks are refused (bandit B314). Fictional XML."""
import pytest
from defusedxml import EntitiesForbidden

from app.rag.pubmed import _parse_articles

ARTICLE = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<ArticleTitle>A fictional review of hypertension</ArticleTitle>
<Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
<Abstract><AbstractText Label="BACKGROUND">Made up for a test.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

BOMB = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>&b;</ArticleTitle>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def test_a_normal_response_is_parsed():
    [article] = _parse_articles(ARTICLE, {"123"})
    assert article.title == "A fictional review of hypertension" and article.year == "2024"


def test_entity_expansion_is_refused():
    with pytest.raises(EntitiesForbidden):
        _parse_articles(BOMB, {"1"})
