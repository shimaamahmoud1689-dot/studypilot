import pymupdf
import json
import os
import re


# 0. Clean text
def clean_text(text):
    # remove leftover PowerPoint placeholder text
    text = text.replace("Type equation here.", "")
    # fix split numbers like "1 5%" -> "15%"
    text = re.sub(r'(\d)\s+(\d)(?=\s*%)', r'\1\2', text)
    # collapse extra spaces and new lines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# 1. Extract text from PDF and keep page numbers
def extract_pages(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages = []

    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = clean_text(page.get_text())

            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


# 2. Split text into chunks
def chunk_pages(pages, size=100, overlap=20):
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Invalid chunk size or overlap")

    chunks = []
    step = size - overlap

    for page in pages:
        words = page["text"].split()

        for i in range(0, len(words), step):
            piece = " ".join(words[i:i + size])

            if piece:
                chunks.append({
                    "chunk_id": len(chunks) + 1,
                    "page": page["page"],
                    "text": piece
                })

    return chunks


# 3. Save data to JSON
def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# 4. Main function
def main():
    pdf_path = "lecture.pdf"

    try:
        pages = extract_pages(pdf_path)
        chunks = chunk_pages(pages, size=100, overlap=20)

        save_json(pages, "extracted_pages.json")
        save_json(chunks, "chunks.json")

        print("PDF processing completed successfully!")
        print("Number of pages:", len(pages))
        print("Number of chunks:", len(chunks))
        print("Saved: extracted_pages.json")
        print("Saved: chunks.json")

        empty_pages = [p["page"] for p in pages if not p["text"]]

        if len(empty_pages) == len(pages):
            print("WARNING: This PDF looks scanned (images only). Use another PDF or OCR.")
        elif empty_pages:
            print("Pages with no extractable text:", empty_pages)

        print("\nTesting chunks...")
        if chunks:
            for chunk in chunks[:3]:
                print("\nChunk ID:", chunk["chunk_id"])
                print("Page:", chunk["page"])
                print("Text:", chunk["text"][:100])
        
        else:
            print("No text chunks found in the PDF.")

    except (FileNotFoundError, ValueError, pymupdf.FileDataError) as error:
        print("Error:", error)


if __name__ == "__main__":
    main()
