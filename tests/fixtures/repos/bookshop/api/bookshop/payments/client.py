import httpx

CHARGES_URL = "https://payments.example/v1/charges"


class PaymentsClient:
    """Calls the card payment provider."""

    def charge(self, card_token: str, amount_cents: int) -> str:
        response = httpx.post(CHARGES_URL, json={"source": card_token, "amount": amount_cents})
        response.raise_for_status()
        return response.json()["id"]
