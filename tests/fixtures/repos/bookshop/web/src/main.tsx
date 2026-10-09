import { createRoot } from "react-dom/client";
import { useState } from "react";

import { Book, placeOrder, searchBooks } from "./api/client";

function App() {
  const [books, setBooks] = useState<Book[]>([]);
  return (
    <main>
      <input placeholder="Search books" onChange={async (e) => setBooks(await searchBooks(e.target.value))} />
      <ul>
        {books.map((book) => (
          <li key={book.id}>
            {book.title} by {book.author}
            <button onClick={() => placeOrder(book.id, 1, "card-token")}>Buy</button>
          </li>
        ))}
      </ul>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
