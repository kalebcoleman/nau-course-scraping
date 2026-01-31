import re
import time
import csv
import sys
import os
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# =========================
# CONFIG
# =========================

BASE = "https://catalog.nau.edu/Courses"

TERM_CODES = {
    "Fall 2025": 1257,
    "Spring 2026": 1261,
}

CSV_PATH = "nau_courses.csv"
EMPTY_PREFIXES_CSV = "nau_empty_prefixes.csv"

OVERWRITE = "--overwrite" in sys.argv
HEADLESS = "--no-headless" not in sys.argv

SLEEP_TIME = 0.25

# =========================
# COURSE PREFIXES (NAU)
# =========================

PREFIXES = [
    "ACC",
    "ACM",
    "ADM",
    "ADV",
    "AHB",
    "AIS",
    "ANS",
    "ANT",
    "APMS",
    "ARB",
    "ARE",
    "ARH",
    "ART",
    "AS",
    "ASN",
    "AST",
    "AT",
    "BA",
    "BASW",
    "BBA",
    "BE",
    "BIO",
    "BME",
    "BSC",
    "BSCI",
    "BUS",
    "CAL",
    "CCHE",
    "CCJ",
    "CCS",
    "CENE",
    "CENS",
    "CHI",
    "CHM",
    "CIE",
    "CINE",
    "CIT",
    "CLA",
    "CM",
    "CMF",
    "COM",
    "CPP",
    "CS",
    "CSD",
    "CST",
    "CTE",
    "CYB",
    "DH",
    "DIS",
    "ECI",
    "ECO",
    "EDF",
    "EDL",
    "EDR",
    "EDU",
    "EE",
    "EES",
    "EET",
    "EGR",
    "EIT",
    "EMF",
    "EMGT",
    "ENG",
    "ENT",
    "ENTY",
    "ENV",
    "ENVY",
    "EPS",
    "ES",
    "ESE",
    "ETC",
    "FIN",
    "FIT",
    "FOR",
    "FRE",
    "FW",
    "FYS",
    "GCS",
    "GER",
    "GLG",
    "GRK",
    "GSP",
    "HA",
    "HHS",
    "HIS",
    "HISY",
    "HON",
    "HPI",
    "HS",
    "HUM",
    "IBH",
    "ICJ",
    "ID",
    "IH",
    "INF",
    "INT",
    "ISM",
    "ITA",
    "ITG",
    "JLS",
    "JPN",
    "JUS",
    "LAN",
    "LAS",
    "LAT",
    "LEA",
    "MAT",
    "ME",
    "MER",
    "MGBA",
    "MGT",
    "MKT",
    "MOL",
    "MS",
    "MST",
    "MUP",
    "MUS",
    "NAU",
    "NAUY",
    "NAV",
    "NSE",
    "NTS",
    "NUR",
    "OTD",
    "PADM",
    "PE",
    "PHA",
    "PHI",
    "PHO",
    "PHS",
    "PHY",
    "POR",
    "PM",
    "POS",
    "PR",
    "PRM",
    "PSY",
    "PT",
    "REL",
    "RUS",
    "SA",
    "SBA",
    "SBS",
    "SE",
    "SIMY",
    "SOC",
    "SOCIO",
    "SPA",
    "SST",
    "STA",
    "STR",
    "SUS",
    "SW",
    "SYS",
    "TH",
    "TRAN",
    "TSM",
    "USC",
    "VC",
    "WGS",
]

# =========================
# DATA MODEL
# =========================


@dataclass
class Course:
    term: str
    catalog_year: Optional[str]
    prefix: str
    number: str
    title: str
    description: Optional[str]
    units: Optional[str]
    sections_offered: Optional[str]
    url: str


# =========================
# UTILS
# =========================


def polite_sleep():
    time.sleep(SLEEP_TIME)


def make_driver():
    opts = webdriver.ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


def results_url(prefix: str, term_code: int) -> str:
    return f"{BASE}/results?subject={prefix}&catNbr=&term={term_code}"


def load_existing_courses() -> Dict[str, Dict]:
    """
    Load existing CSV into dict keyed by URL
    """
    existing = {}
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["url"]] = row
        print(f"Loaded {len(existing)} existing courses from {CSV_PATH}")
    except FileNotFoundError:
        print("No existing CSV found — starting fresh.")
    return existing


def write_csv(rows: Dict[str, Dict]):
    """
    Rewrite full CSV (safe overwrite)
    """
    if not rows:
        return

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[next(iter(rows))].keys())
        writer.writeheader()
        writer.writerows(rows.values())


def log_empty_prefix(term_label: str, term_code: int, prefix: str, error: str):
    write_header = not os.path.exists(EMPTY_PREFIXES_CSV)
    with open(EMPTY_PREFIXES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["term", "term_code", "prefix", "error"]
        )
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "term": term_label,
                "term_code": term_code,
                "prefix": prefix,
                "error": error,
            }
        )


# =========================
# SCRAPING HELPERS
# =========================


def get_course_links(
    driver, prefix: str, term_code: int, retries: int = 2, wait_s: int = 15
) -> List[str]:
    for attempt in range(retries + 1):
        driver.get(results_url(prefix, term_code))
        wait = WebDriverWait(driver, wait_s)

        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "dl#results-list dt.result-item > a")
                    ),
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@id='main']//h1[normalize-space()='No courses found']")
                    ),
                )
            )
        except TimeoutException:
            if attempt < retries:
                continue
            print(f"[WARN] {prefix} list timed out; skipping")
            return []

        # If the "no courses found" message is present, return empty list immediately.
        try:
            driver.find_element(
                By.XPATH, "//div[@id='main']//h1[normalize-space()='No courses found']"
            )
            return []
        except Exception:
            pass

        links = set()
        for a in driver.find_elements(
            By.CSS_SELECTOR, "dl#results-list dt.result-item > a"
        ):
            href = a.get_attribute("href")
            if href:
                if href.startswith("course?"):
                    href = f"{BASE}/{href}"
                links.add(href)

        return sorted(links)

    return []


def text_after_label(driver, label: str) -> Optional[str]:
    try:
        strong = driver.find_element(
            By.XPATH,
            f"//div[@id='courseResults']//strong[normalize-space()='{label}:']",
        )
    except Exception:
        return None

    try:
        # Walk DOM siblings to capture text nodes or element text.
        return driver.execute_script(
            """
            let node = arguments[0].nextSibling;
            while (node) {
              const text = (node.textContent || '').trim();
              if (text) return text;
              node = node.nextSibling;
            }
            return null;
            """,
            strong,
        )
    except Exception:
        return None


def get_catalog_year(driver) -> Optional[str]:
    try:
        txt = driver.find_element(By.CSS_SELECTOR, "#h1-first").text
        m = re.search(r"Catalog Year\s*:\s*([0-9]{4}\s*-\s*[0-9]{4})", txt)
        if m:
            return m.group(1).replace(" ", "")
    except Exception:
        pass
    return None


def get_sections_offered(driver) -> Optional[str]:
    try:
        anchors = driver.find_elements(
            By.XPATH,
            "//div[@id='courseResults']//strong[normalize-space()='Sections offered:']/following-sibling::a",
        )
        texts = [a.text.strip() for a in anchors if a.text.strip()]
        return "; ".join(texts) if texts else None
    except Exception:
        return None


def scrape_course(driver, url: str, term_label: str) -> Course:
    driver.get(url)
    wait = WebDriverWait(driver, 15)

    h2 = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#courseResults h2"))
    )
    header = h2.text.strip()

    m = re.match(r"^([A-Z&]{2,6})\s+(\d{3}[A-Z]?)\s*-\s*(.+)$", header)
    prefix, number, title = ("", "", header)
    if m:
        prefix, number, title = m.group(1), m.group(2), m.group(3).strip()

    course = Course(
        term=term_label,
        catalog_year=get_catalog_year(driver),
        prefix=prefix,
        number=number,
        title=title,
        description=text_after_label(driver, "Description"),
        units=text_after_label(driver, "Units"),
        sections_offered=get_sections_offered(driver),
        url=url,
    )

    polite_sleep()
    return course


# =========================
# MAIN
# =========================


def main():
    existing = load_existing_courses()
    driver = make_driver()

    try:
        total_prefixes = len(PREFIXES) * len(TERM_CODES)
        step = 1

        for term_label, term_code in TERM_CODES.items():
            for prefix in PREFIXES:
                print(
                    f"[{step}/{total_prefixes}] {term_label} {prefix}: fetching list..."
                )
                links = get_course_links(driver, prefix, term_code)
                print(
                    f"[{step}/{total_prefixes}] {term_label} {prefix}: {len(links)} courses"
                )

                if not links:
                    log_empty_prefix(
                        term_label,
                        term_code,
                        prefix,
                        "empty",
                    )
                    step += 1
                    continue

                new_count = 0

                for link in links:
                    if link in existing and not OVERWRITE:
                        continue

                    try:
                        course = scrape_course(driver, link, term_label)
                        existing[link] = asdict(course)
                        new_count += 1
                    except Exception as e:
                        print(f"[WARN] Failed {link}: {e}")

                print(
                    f"[{step}/{total_prefixes}] {term_label} {prefix}: {new_count} new/updated courses"
                )

                write_csv(existing)
                step += 1

    finally:
        driver.quit()

    print(f"Finished. Total courses in CSV: {len(existing)}")


if __name__ == "__main__":
    main()
