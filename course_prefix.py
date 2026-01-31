import re
import pdfplumber

# IMPORTANT: set this to the exact filename/path you have
PDF_PATH = "Course-Numbering-and-Prefixes.pdf"  # <-- update if needed


def extract_prefixes(pdf_path: str) -> list[str]:
    prefixes = set()

    # Table rows look like: "ACC Accounting" :contentReference[oaicite:1]{index=1}
    pat = re.compile(r"^([A-Z&]{2,6})\s+([A-Za-z].+)$")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                m = pat.match(line)
                if not m:
                    continue
                code, subject = m.group(1), m.group(2).strip()

                # skip headers/noise
                if code in {"Course", "Code", "Subject", "Letter"}:
                    continue
                if not code.isalpha() and "&" not in code:
                    continue

                prefixes.add(code)

    return sorted(prefixes)


if __name__ == "__main__":
    prefixes = extract_prefixes(PDF_PATH)
    print(f"Found {len(prefixes)} prefixes")
    print("PREFIXES = [")
    for p in prefixes:
        print(f"    '{p}',")
    print("]")
