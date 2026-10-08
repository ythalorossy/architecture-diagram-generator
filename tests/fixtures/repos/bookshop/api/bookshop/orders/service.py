import os

import psycopg

from bookshop.payments.client import PaymentsClient


class OrderRepository:
    """Stores orders in the bookshop's own PostgreSQL database."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def save(self, book_id: str, quantity: int, charge_id: str) -> int:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "INSERT INTO orders (book_id, quantity, charge_id) VALUES (%s, %s, %s) RETURNING id",
                (book_id, quantity, charge_id),
            ).fetchone()
            return row[0]


class OrderService:
    """Takes payment for an order, then records it."""

    def __init__(self, repository: OrderRepository = None, payments: PaymentsClient = None):
        self.repository = repository or OrderRepository(os.environ["DATABASE_URL"])
        self.payments = payments or PaymentsClient()

    def place(self, book_id: str, quantity: int, card_token: str) -> dict:
        charge_id = self.payments.charge(card_token, quantity * 1200)
        order_id = self.repository.save(book_id, quantity, charge_id)
        return {"order_id": order_id, "charge_id": charge_id}
