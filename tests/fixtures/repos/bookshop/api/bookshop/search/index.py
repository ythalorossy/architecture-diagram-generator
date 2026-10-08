import os

from elasticsearch import Elasticsearch


class CatalogIndex:
    """Searches the book catalogue index, which the catalogue team runs and fills."""

    def __init__(self, url: str = None):
        self.client = Elasticsearch(url or os.environ["SEARCH_URL"])

    def search(self, text: str) -> list:
        result = self.client.search(index="books", query={"match": {"title": text}})
        return [hit["_source"] for hit in result["hits"]["hits"]]
