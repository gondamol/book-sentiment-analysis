#!/usr/bin/env python3
"""Build processed survey-insights assets from a raw XLSX workbook.

This parser intentionally avoids openpyxl so it can run in lightweight
environments where only the Python standard library is available.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Iterator, List
import xml.etree.ElementTree as ET

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ROW_TAG = f"{{{NS}}}row"
CELL_TAG = f"{{{NS}}}c"
VALUE_TAG = f"{{{NS}}}v"
TEXT_TAG = f"{{{NS}}}t"
CELL_RE = re.compile(r"([A-Z]+)(\d+)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")

DATE_COLUMNS = {"C", "F", "Y", "AD"}

COUNTY_ALIASES = {
    "homabay": "Homa Bay",
    "homa bay": "Homa Bay",
    "nairobi city": "Nairobi",
}

THEMES = {
    "staff_attitude": {
        "label": "Staff attitude and respect",
        "keywords": [
            "friendly",
            "welcoming",
            "caring",
            "respect",
            "rude",
            "attitude",
            "provider",
            "providers",
            "staff",
            "staffs",
            "doctor",
            "doctors",
            "nurse",
            "nurses",
            "reception",
            "kind",
        ],
    },
    "wait_time": {
        "label": "Waiting time and flow",
        "keywords": [
            "waiting",
            "queue",
            "delay",
            "delays",
            "long time",
            "timely",
            "faster",
            "slow",
            "quick",
            "fast",
        ],
    },
    "medicines_supplies": {
        "label": "Medicines and supplies",
        "keywords": [
            "drug",
            "drugs",
            "medicine",
            "medicines",
            "kit",
            "kits",
            "stock",
            "stockout",
            "stock out",
            "viral load",
            "septrin",
            "test tube",
            "supplement",
            "supplements",
        ],
    },
    "food_transport_support": {
        "label": "Food and transport support",
        "keywords": [
            "food",
            "transport",
            "fare",
            "allowance",
            "nutrition",
            "nutritional",
            "flour",
            "plumpy",
            "support",
            "feeding",
        ],
    },
    "equipment_space": {
        "label": "Equipment and infrastructure",
        "keywords": [
            "equipment",
            "equipments",
            "machine",
            "machines",
            "laboratory",
            "lab",
            "space",
            "room",
            "infrastructure",
            "building",
            "expansion",
            "computer",
            "weight machine",
        ],
    },
    "confidentiality_stigma": {
        "label": "Confidentiality and stigma",
        "keywords": [
            "privacy",
            "confidentiality",
            "confidential",
            "stigma",
            "disclosure",
            "secret",
            "secrecy",
        ],
    },
    "access_cost": {
        "label": "Access and affordability",
        "keywords": [
            "access",
            "distance",
            "cost",
            "expensive",
            "afford",
            "referral",
            "referrals",
            "travel",
            "transport",
        ],
    },
    "counseling_mental_health": {
        "label": "Counseling and mental wellbeing",
        "keywords": [
            "counseling",
            "counselling",
            "psychosocial",
            "psychological",
            "mental",
            "emotional",
            "depression",
            "anxiety",
            "gbv",
            "violence",
        ],
    },
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "have",
    "has",
    "had",
    "their",
    "they",
    "them",
    "your",
    "from",
    "there",
    "would",
    "should",
    "were",
    "been",
    "into",
    "about",
    "while",
    "what",
    "which",
    "when",
    "where",
    "because",
    "facility",
    "facilities",
    "service",
    "services",
    "care",
    "treatment",
    "client",
    "clients",
    "received",
    "accessing",
    "provided",
    "would",
    "like",
    "please",
    "specify",
    "comment",
    "comments",
    "none",
    "nothing",
}

QUOTE_SKIP = {
    "",
    "none",
    "none observed",
    "nothing",
    "no additional information",
    "no comments",
    "comments",
    "comment",
    "nil",
    "n/a",
}


@dataclass
class BuildResult:
    records: List[dict]
    analysis: dict


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def excel_to_iso(value: str) -> str:
    value = normalize_text(value)
    if not value:
        return ""
    try:
        serial = float(value)
    except ValueError:
        return value
    if serial <= 0:
        return value
    base = datetime(1899, 12, 30)
    stamp = base + timedelta(days=serial)
    if abs(serial - int(serial)) < 1e-9:
        return stamp.strftime("%Y-%m-%d")
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def parse_date(value: str) -> datetime | None:
    value = normalize_text(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def month_key(value: str) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m") if parsed else "Unknown"


def normalize_county(value: str) -> str:
    value = normalize_text(value)
    if not value:
        return "Unknown"
    lowered = value.lower()
    return COUNTY_ALIASES.get(lowered, value.title() if value.islower() else value)


def pick_first(*values: str) -> str:
    for value in values:
        value = normalize_text(value)
        if value:
            return value
    return ""


def age_group_from_birthdate(birthdate: str, reference_date: str, fallback: str) -> str:
    fallback = normalize_text(fallback)
    if fallback:
        return fallback
    birth = parse_date(birthdate)
    ref = parse_date(reference_date)
    if birth is None or ref is None:
        return "Unknown"
    age = ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))
    if age < 18:
        return "Under 18"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    if age <= 54:
        return "45-54"
    if age <= 64:
        return "55-64"
    return "65+"


def survey_group(name: str) -> str:
    lowered = name.lower()
    if "app quality" in lowered:
        return "Digital experience"
    if "mental health" in lowered or "covid" in lowered:
        return "Mental health and community support"
    return "Facility service experience"


def canonical_yes_no(value: str) -> str:
    value = normalize_text(value).lower()
    if not value:
        return "Unknown"
    if value.startswith("yes"):
        return "Yes"
    if value.startswith("no"):
        return "No"
    if "not sure" in value or "don't know" in value or "do not know" in value or "am not sure" in value or "i am not sure" in value:
        return "Not sure"
    if value in {"true", "adequate", "available", "sufficient"}:
        return "Yes"
    if any(token in value for token in ("inadequate", "not enough", "insufficient", "lacks", "lack of", "missing")):
        return "No"
    return "Other"


def canonical_satisfaction(value: str) -> str:
    value = normalize_text(value).lower()
    if not value:
        return "Unknown"
    if "very satisfied" in value:
        return "Very satisfied"
    if "satisfied" in value:
        return "Satisfied"
    if "unsatisfied" in value or "dissatisfied" in value:
        return "Dissatisfied"
    if "prefer not" in value:
        return "Prefer not to answer"
    if "do not know" in value or "don't know" in value:
        return "Do not know"
    return value.title()


def sentiment_label(score: float) -> str:
    if score >= 0.2:
        return "Positive"
    if score <= -0.2:
        return "Negative"
    return "Mixed / Neutral"


def tag_themes(text: str) -> List[str]:
    lowered = normalize_text(text).lower()
    matches: List[str] = []
    if not lowered:
        return matches
    for theme_id, config in THEMES.items():
        if any(keyword in lowered for keyword in config["keywords"]):
            matches.append(theme_id)
    return matches


def tokenize(text: str) -> List[str]:
    words = [match.group(0).lower() for match in WORD_RE.finditer(text)]
    return [word for word in words if len(word) > 2 and word not in STOPWORDS]


def shared_strings(workbook: zipfile.ZipFile) -> List[str]:
    values: List[str] = []
    with workbook.open("xl/sharedStrings.xml") as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if element.tag == f"{{{NS}}}si":
                values.append("".join(node.text or "" for node in element.iter(TEXT_TAG)))
                element.clear()
    return values


def iter_rows(path: Path) -> Iterator[Dict[str, str]]:
    with zipfile.ZipFile(path) as workbook:
        strings = shared_strings(workbook)
        with workbook.open("xl/worksheets/sheet1.xml") as handle:
            for _, element in ET.iterparse(handle, events=("end",)):
                if element.tag != ROW_TAG:
                    continue
                row: Dict[str, str] = {}
                for cell in element.findall(CELL_TAG):
                    ref = cell.attrib.get("r", "")
                    match = CELL_RE.match(ref)
                    if not match:
                        continue
                    column = match.group(1)
                    cell_type = cell.attrib.get("t")
                    value = ""
                    raw_value = cell.find(VALUE_TAG)
                    if cell_type == "s" and raw_value is not None and raw_value.text:
                        value = strings[int(raw_value.text)]
                    elif cell_type == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter(TEXT_TAG))
                    elif raw_value is not None and raw_value.text:
                        value = raw_value.text
                    if column in DATE_COLUMNS:
                        value = excel_to_iso(value)
                    row[column] = normalize_text(value)
                element.clear()
                yield row


def normalize_record(row: Dict[str, str], analyzer: SentimentIntensityAnalyzer) -> dict:
    response_date = pick_first(row.get("Y", ""), row.get("C", ""))
    county = normalize_county(pick_first(row.get("AC", ""), row.get("AI", ""), row.get("CL", "")))
    facility_name = pick_first(row.get("AQ", ""), row.get("Z", ""))
    gender = pick_first(row.get("CM", ""), row.get("AE", ""))
    age_group = age_group_from_birthdate(row.get("AD", ""), response_date, row.get("CJ", ""))
    survey_name = normalize_text(row.get("D", "")) or "Unknown"

    positive_text = pick_first(row.get("AU", ""), row.get("CE", ""))
    concern_text = row.get("AV", "")
    improvement_text = pick_first(row.get("AW", ""), row.get("CF", ""))
    access_text = row.get("BA", "")
    additional_text = row.get("CG", "")
    highlight_text = row.get("CH", "")
    mental_challenges = row.get("Q", "")
    mental_support = row.get("R", "")
    mental_response = row.get("S", "")
    mental_support_needed = row.get("T", "")

    combined_feedback = normalize_text(
        " ".join(
            value
            for value in [
                positive_text,
                concern_text,
                improvement_text,
                access_text,
                highlight_text,
                additional_text,
                mental_challenges,
                mental_support,
                mental_response,
                mental_support_needed,
            ]
            if normalize_text(value)
        )
    )
    snippet = pick_first(concern_text, improvement_text, access_text, highlight_text, additional_text, positive_text, mental_challenges)
    score = analyzer.polarity_scores(combined_feedback)["compound"] if combined_feedback else 0.0
    themes = tag_themes(combined_feedback)

    return {
        "response_id": normalize_text(row.get("A", "")),
        "user_id": normalize_text(row.get("B", "")),
        "survey_name": survey_name,
        "survey_group": survey_group(survey_name),
        "channel_type": normalize_text(row.get("E", "")),
        "response_date": response_date,
        "response_month": month_key(response_date),
        "county": county,
        "sub_county": normalize_text(row.get("CO", "")),
        "organization": normalize_text(row.get("W", "")),
        "facility_name": facility_name or "Unknown",
        "facility_ownership": normalize_text(row.get("AA", "")) or "Unknown",
        "gender": gender or "Unknown",
        "age_group": age_group,
        "education_level": normalize_text(row.get("AF", "")) or "Unknown",
        "marital_status": normalize_text(row.get("AH", "")) or "Unknown",
        "user_type": normalize_text(row.get("CK", "")) or "Unknown",
        "satisfaction": canonical_satisfaction(row.get("AT", "")),
        "access_challenge": canonical_yes_no(row.get("AX", "")),
        "equipment_adequate": canonical_yes_no(row.get("BB", "")),
        "confidentiality": canonical_yes_no(row.get("BC", "")),
        "rights_awareness": canonical_yes_no(row.get("BI", "")),
        "comfortable_at_facility": canonical_yes_no(row.get("BL", "")),
        "counseled": canonical_yes_no(row.get("BN", "")),
        "positive_text": positive_text,
        "concern_text": concern_text,
        "improvement_text": improvement_text,
        "access_text": access_text,
        "highlight_text": highlight_text,
        "additional_text": additional_text,
        "mental_challenges": mental_challenges,
        "mental_support_sought": mental_support,
        "mental_network_response": mental_response,
        "mental_support_needed": mental_support_needed,
        "combined_feedback": combined_feedback,
        "snippet": snippet[:260],
        "sentiment_score": round(score, 4),
        "sentiment_label": sentiment_label(score),
        "themes": themes,
    }


def to_share(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def top_terms(records: Iterable[dict], field_name: str, limit: int = 15) -> List[dict]:
    counts = Counter()
    for record in records:
        counts.update(tokenize(record.get(field_name, "")))
    return [{"term": term, "count": count} for term, count in counts.most_common(limit)]


def quote_text(record: dict, text_fields: List[str]) -> str:
    for field in text_fields:
        value = normalize_text(record.get(field, ""))
        if value and value.lower() not in QUOTE_SKIP:
            return value
    return ""


def best_quotes(records: Iterable[dict], *, score_direction: str, text_fields: List[str], limit: int = 8) -> List[dict]:
    ranked = sorted(
        (
            record
            for record in records
            if quote_text(record, text_fields)
            and len(record["combined_feedback"]) >= 25
        ),
        key=lambda item: item["sentiment_score"],
        reverse=(score_direction == "desc"),
    )
    seen = set()
    quotes = []
    for record in ranked:
        text = quote_text(record, text_fields)
        key = (text, record["county"], record["survey_name"])
        if key in seen:
            continue
        seen.add(key)
        quotes.append(
            {
                "survey_name": record["survey_name"],
                "county": record["county"],
                "snippet": text[:260],
                "sentiment_score": record["sentiment_score"],
                "themes": record["themes"],
            }
        )
        if len(quotes) >= limit:
            break
    return quotes


def compact_record(record: dict) -> dict:
    return {
        "response_id": record["response_id"],
        "survey_name": record["survey_name"],
        "survey_group": record["survey_group"],
        "response_date": record["response_date"],
        "response_month": record["response_month"],
        "county": record["county"],
        "sub_county": record["sub_county"],
        "organization": record["organization"],
        "facility_name": record["facility_name"],
        "facility_ownership": record["facility_ownership"],
        "gender": record["gender"],
        "age_group": record["age_group"],
        "user_type": record["user_type"],
        "satisfaction": record["satisfaction"],
        "access_challenge": record["access_challenge"],
        "equipment_adequate": record["equipment_adequate"],
        "confidentiality": record["confidentiality"],
        "rights_awareness": record["rights_awareness"],
        "comfortable_at_facility": record["comfortable_at_facility"],
        "counseled": record["counseled"],
        "sentiment_score": record["sentiment_score"],
        "sentiment_label": record["sentiment_label"],
        "themes": record["themes"],
        "snippet": record["snippet"],
    }


def build_analysis(records: List[dict], source_file: Path) -> dict:
    survey_counts = Counter(record["survey_name"] for record in records)
    county_counts = Counter(record["county"] for record in records)
    gender_counts = Counter(record["gender"] for record in records)
    age_counts = Counter(record["age_group"] for record in records)
    sentiment_counts = Counter(record["sentiment_label"] for record in records)
    satisfaction_counts = Counter(record["satisfaction"] for record in records)
    theme_counts = Counter()
    monthly: Dict[str, dict] = defaultdict(lambda: {"responses": 0, "sentiment_sum": 0.0, "positive_satisfaction": 0, "access_challenges": 0})
    survey_profiles: Dict[str, dict] = {}

    for record in records:
        for theme in record["themes"]:
            theme_counts[theme] += 1

        month = record["response_month"]
        monthly[month]["responses"] += 1
        monthly[month]["sentiment_sum"] += record["sentiment_score"]
        if record["satisfaction"] in {"Satisfied", "Very satisfied"}:
            monthly[month]["positive_satisfaction"] += 1
        if record["access_challenge"] == "Yes":
            monthly[month]["access_challenges"] += 1

    for survey_name, count in survey_counts.items():
        subset = [record for record in records if record["survey_name"] == survey_name]
        survey_profiles[survey_name] = {
            "responses": count,
            "avg_sentiment": round(sum(item["sentiment_score"] for item in subset) / count, 3),
            "positive_satisfaction_share": to_share(
                sum(1 for item in subset if item["satisfaction"] in {"Satisfied", "Very satisfied"}),
                count,
            ),
            "access_challenge_share": to_share(
                sum(1 for item in subset if item["access_challenge"] == "Yes"),
                count,
            ),
            "top_county": Counter(item["county"] for item in subset).most_common(1)[0][0],
        }

    total = len(records)
    analysis = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source_file": source_file.name,
        "response_count": total,
        "survey_counts": [{"name": name, "count": count} for name, count in survey_counts.most_common()],
        "county_counts": [{"name": name, "count": count} for name, count in county_counts.most_common(12)],
        "gender_counts": [{"name": name, "count": count} for name, count in gender_counts.most_common()],
        "age_group_counts": [{"name": name, "count": count} for name, count in age_counts.most_common()],
        "sentiment_counts": [{"name": name, "count": count} for name, count in sentiment_counts.items()],
        "satisfaction_counts": [{"name": name, "count": count} for name, count in satisfaction_counts.items()],
        "metrics": {
            "avg_sentiment": round(sum(record["sentiment_score"] for record in records) / total, 3),
            "positive_satisfaction_share": to_share(
                sum(1 for record in records if record["satisfaction"] in {"Satisfied", "Very satisfied"}),
                total,
            ),
            "access_challenge_share": to_share(
                sum(1 for record in records if record["access_challenge"] == "Yes"),
                total,
            ),
            "confidentiality_yes_share": to_share(
                sum(1 for record in records if record["confidentiality"] == "Yes"),
                total,
            ),
            "rights_awareness_share": to_share(
                sum(1 for record in records if record["rights_awareness"] == "Yes"),
                total,
            ),
        },
        "monthly_trend": [
            {
                "month": month,
                "responses": values["responses"],
                "avg_sentiment": round(values["sentiment_sum"] / values["responses"], 3),
                "positive_satisfaction_share": to_share(values["positive_satisfaction"], values["responses"]),
                "access_challenge_share": to_share(values["access_challenges"], values["responses"]),
            }
            for month, values in sorted(monthly.items())
            if month != "Unknown"
        ],
        "theme_overview": [
            {
                "theme_id": theme_id,
                "label": THEMES[theme_id]["label"],
                "count": count,
                "share": to_share(count, total),
            }
            for theme_id, count in theme_counts.most_common()
        ],
        "survey_profiles": survey_profiles,
        "top_terms": {
            "positive": top_terms(records, "positive_text"),
            "concerns": top_terms(records, "concern_text"),
            "improvements": top_terms(records, "improvement_text"),
            "access": top_terms(records, "access_text"),
            "mental_health": top_terms(records, "mental_challenges"),
        },
        "quotes": {
            "positive": best_quotes(
                records,
                score_direction="desc",
                text_fields=["positive_text", "highlight_text"],
            ),
            "improvement": best_quotes(
                records,
                score_direction="asc",
                text_fields=["concern_text", "improvement_text", "access_text", "additional_text", "mental_challenges"],
            ),
        },
        "theme_quotes": {
            theme_id: best_quotes(
                [record for record in records if theme_id in record["themes"]],
                score_direction="desc",
                text_fields=["positive_text", "highlight_text", "improvement_text", "concern_text"],
                limit=4,
            )
            for theme_id in theme_counts
        },
    }
    return analysis


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def write_csv(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "response_id",
        "survey_name",
        "survey_group",
        "response_date",
        "response_month",
        "county",
        "sub_county",
        "organization",
        "facility_name",
        "facility_ownership",
        "gender",
        "age_group",
        "education_level",
        "marital_status",
        "user_type",
        "satisfaction",
        "access_challenge",
        "equipment_adequate",
        "confidentiality",
        "rights_awareness",
        "comfortable_at_facility",
        "counseled",
        "sentiment_score",
        "sentiment_label",
        "themes",
        "snippet",
        "positive_text",
        "concern_text",
        "improvement_text",
        "access_text",
        "highlight_text",
        "additional_text",
        "mental_challenges",
        "mental_support_sought",
        "mental_network_response",
        "mental_support_needed",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["themes"] = ", ".join(record["themes"])
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_assets(source_file: Path, output_dir: Path) -> BuildResult:
    analyzer = SentimentIntensityAnalyzer()
    rows = iter_rows(source_file)
    header = next(rows)
    if header.get("A") != "Survey ID":
        raise ValueError("Unexpected workbook format: first row does not look like the survey header")

    records = [normalize_record(row, analyzer) for row in rows]
    analysis = build_analysis(records, source_file)

    processed_dir = output_dir / "data" / "processed"
    app_assets_dir = output_dir / "app" / "assets"

    write_json(processed_dir / "records.json", records)
    write_json(processed_dir / "analysis.json", analysis)
    write_csv(processed_dir / "records.csv", records)

    write_json(app_assets_dir / "records.json", [compact_record(record) for record in records])
    write_json(app_assets_dir / "analysis.json", analysis)
    write_csv(app_assets_dir / "records.csv", records)

    return BuildResult(records=records, analysis=analysis)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build survey insight assets from a raw Excel workbook.")
    parser.add_argument(
        "--input",
        default="/home/gondamol/sentiment-analysis-projects/Survey_04_04_2023, 23_09_23.xlsx",
        help="Path to the XLSX workbook to parse.",
    )
    parser.add_argument(
        "--output-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Root directory for the survey_insights project.",
    )
    args = parser.parse_args()

    source_file = Path(args.input).expanduser().resolve()
    if not source_file.exists():
        raise FileNotFoundError(f"Workbook not found: {source_file}")

    result = build_assets(source_file, args.output_root)
    print(f"Built {len(result.records)} survey records from {source_file.name}")
    print(f"Wrote assets to {args.output_root / 'data' / 'processed'} and {args.output_root / 'app' / 'assets'}")


if __name__ == "__main__":
    main()
