from fastapi import FastAPI

from bookshop.orders.service import OrderService
from bookshop.search.index import CatalogIndex

app = FastAPI(title="Bookshop API")
orders = OrderService()
catalog = CatalogIndex()


@app.get("/api/books")
def search_books(q: str = ""):
    return catalog.search(q)


@app.post("/api/orders")
def place_order(order: dict):
    return orders.place(order["book_id"], order["quantity"], order["card_token"])
