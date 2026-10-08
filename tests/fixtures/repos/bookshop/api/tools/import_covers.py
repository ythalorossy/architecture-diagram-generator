"""One-off script, run by hand: downloads cover images for books that have none."""
import sys

import httpx

COVERS_URL = "https://covers.example/v2/isbn/{isbn}.jpg"


def main(isbns):
    for isbn in isbns:
        image = httpx.get(COVERS_URL.format(isbn=isbn)).content
        with open(f"covers/{isbn}.jpg", "wb") as file:
            file.write(image)


if __name__ == "__main__":
    main(sys.argv[1:])
