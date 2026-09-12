import requests
from bs4 import BeautifulSoup
import yaml
import uuid

def fetch_page(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text

def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def scrape_all(sources: list[dict]) -> list[dict]:
    documents = []
    for source in sources:
        url = source["url"]
        category = source["category"]
        try:
            html = fetch_page(url)
            text = extract_text(html)
            documents.append({"text": text, "category": category, "url": url})
        except Exception as e:
            print(f"Skipping {url}: {e}")
    return documents
    
def generate_chunk_id(url: str, text: str) -> str:
    combined = url + " " + text
    chunk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, combined)
    return str(chunk_uuid)

def chunk_text(text: str, max_char: int = 800) -> list[str]:
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 1 <= max_char:
            current_chunk += paragraph + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def load_sources(path: str) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
    return data["sources"]