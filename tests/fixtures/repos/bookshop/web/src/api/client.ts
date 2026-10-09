export interface Book {
  id: string;
  title: string;
  author: string;
}

export async function searchBooks(text: string): Promise<Book[]> {
  const response = await fetch(`/api/books?q=${encodeURIComponent(text)}`);
  return response.json();
}

export async function placeOrder(bookId: string, quantity: number, cardToken: string) {
  const response = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ book_id: bookId, quantity, card_token: cardToken }),
  });
  return response.json();
}
