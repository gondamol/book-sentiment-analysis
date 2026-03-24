#!/usr/bin/env python3
"""Generate a donor-ready PDF brief from processed survey insights."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.pdfbase import pdfdoc
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def compat_md5(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return hashlib.md5(*args, **kwargs)


pdfdoc.md5 = compat_md5

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_PATH = ROOT / "data" / "processed" / "analysis.json"
REPORT_PATH = ROOT / "reports" / "usaid-community-feedback-report.pdf"
APP_REPORT_PATH = ROOT / "app" / "assets" / "usaid-community-feedback-report.pdf"

NAVY = colors.HexColor("#122a42")
TEAL = colors.HexColor("#0f8b8d")
RED = colors.HexColor("#c75146")
SAND = colors.HexColor("#f7f1e8")
TEXT = colors.HexColor("#32485d")
LINE = colors.HexColor("#d8e0e7")


def load_analysis() -> dict:
    with ANALYSIS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=NAVY,
            spaceAfter=8,
            spaceBefore=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.4,
            leading=15,
            textColor=TEXT,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Kicker",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=RED,
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CenterNote",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT,
            alignment=TA_CENTER,
        )
    )
    return styles


def page_frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(SAND)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(doc.leftMargin, 1.2 * cm, "Community Feedback and Service Experience Analysis Brief")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def stat_table(metrics: dict, styles) -> Table:
    rows = [
        [
            Paragraph("<b>Total responses</b><br/>23,457 client and community records", styles["Body"]),
            Paragraph(f"<b>Positive satisfaction</b><br/>{metrics['positive_satisfaction_share']}%", styles["Body"]),
        ],
        [
            Paragraph(f"<b>Access challenges reported</b><br/>{metrics['access_challenge_share']}%", styles["Body"]),
            Paragraph(f"<b>Confidentiality respected</b><br/>{metrics['confidentiality_yes_share']}%", styles["Body"]),
        ],
        [
            Paragraph(f"<b>Rights awareness</b><br/>{metrics['rights_awareness_share']}%", styles["Body"]),
            Paragraph(f"<b>Average sentiment score</b><br/>{metrics['avg_sentiment']}", styles["Body"]),
        ],
    ]
    table = Table(rows, colWidths=[8.3 * cm, 8.3 * cm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def simple_table(headers, rows, widths):
    table = Table([headers, *rows], colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def quote_block(title: str, quotes: list[dict], styles) -> list:
    flow = [Paragraph(title, styles["SectionTitle"])]
    for quote in quotes[:3]:
        theme_labels = ", ".join(
            {
                "staff_attitude": "Staff attitude",
                "wait_time": "Waiting time",
                "medicines_supplies": "Medicines and supplies",
                "food_transport_support": "Food and transport support",
                "equipment_space": "Equipment and infrastructure",
                "confidentiality_stigma": "Confidentiality and stigma",
                "access_cost": "Access and affordability",
                "counseling_mental_health": "Counseling and mental wellbeing",
            }.get(theme, theme)
            for theme in (quote.get("themes", []) or ["None"])
        )
        text = (
            f"<b>{quote['county']}</b> | {quote['survey_name']}<br/>"
            f"\"{quote['snippet']}\"<br/>"
            f"<font color='#5e6d7b'>Themes: {theme_labels}</font>"
        )
        box = Table([[Paragraph(text, styles["Body"])]], colWidths=[16.6 * cm], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        flow.extend([box, Spacer(1, 0.2 * cm)])
    return flow


def pie_chart(title: str, items: list[dict], *, width: float = 8.1 * cm, height: float = 6.4 * cm) -> Drawing:
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 10, title, fontName="Helvetica-Bold", fontSize=10, fillColor=NAVY))

    pie = Pie()
    pie.x = 8
    pie.y = 10
    pie.width = 125
    pie.height = 125
    pie.data = [item["count"] for item in items]
    pie.labels = [item["name"] for item in items]
    palette = [TEAL, RED, NAVY, colors.HexColor("#8d99ae"), colors.HexColor("#84a59d")]
    for index, _ in enumerate(items):
        pie.slices[index].fillColor = palette[index % len(palette)]
        pie.slices[index].strokeColor = colors.white
    pie.sideLabels = True
    pie.simpleLabels = False
    pie.slices.strokeWidth = 0.5
    drawing.add(pie)
    return drawing


def vertical_bar_chart(title: str, labels: list[str], values: list[float], *, width: float = 8.1 * cm, height: float = 6.4 * cm) -> Drawing:
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 10, title, fontName="Helvetica-Bold", fontSize=10, fillColor=NAVY))

    chart = VerticalBarChart()
    chart.x = 24
    chart.y = 28
    chart.height = 110
    chart.width = width - 42
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = LINE
    chart.barWidth = 14
    chart.groupSpacing = 8
    chart.bars[0].fillColor = TEAL
    chart.bars[0].strokeColor = TEAL
    drawing.add(chart)
    return drawing


def horizontal_bar_chart(title: str, labels: list[str], values: list[float], *, width: float = 16.4 * cm, height: float = 7.1 * cm) -> Drawing:
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 10, title, fontName="Helvetica-Bold", fontSize=10, fillColor=NAVY))

    chart = HorizontalBarChart()
    chart.x = 110
    chart.y = 24
    chart.height = 112
    chart.width = width - 120
    chart.data = [values[::-1]]
    chart.categoryAxis.categoryNames = labels[::-1]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = LINE
    chart.bars[0].fillColor = RED
    chart.bars[0].strokeColor = RED
    chart.barWidth = 10
    chart.groupSpacing = 4
    drawing.add(chart)
    return drawing


class WordCloudBlock(Flowable):
    def __init__(self, title: str, terms: list[dict], width: float = 8.1 * cm, height: float = 5.7 * cm):
        super().__init__()
        self.title = title
        self.terms = terms[:14]
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setFillColor(colors.white)
        canvas.roundRect(0, 0, self.width, self.height, 10, fill=1, stroke=1)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(12, self.height - 18, self.title)

        if not self.terms:
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(TEXT)
            canvas.drawString(12, self.height / 2, "No terms available")
            canvas.restoreState()
            return

        max_count = max(item["count"] for item in self.terms) or 1
        x = 12
        y = self.height - 40
        line_height = 18
        palette = [TEAL, RED, NAVY, colors.HexColor("#6c757d")]

        for index, item in enumerate(self.terms):
            size = 10 + int((item["count"] / max_count) * 10)
            word = item["term"]
            word_width = len(word) * (size * 0.42)
            if x + word_width > self.width - 16:
                x = 12
                y -= line_height
                line_height = 18
            if y < 20:
                break
            canvas.setFont("Helvetica-Bold", size)
            canvas.setFillColor(palette[index % len(palette)])
            canvas.drawString(x, y, word)
            x += word_width + 10
            line_height = max(line_height, size + 4)
        canvas.restoreState()


def build_story(analysis: dict, styles) -> list:
    survey_rows = [
        [row["name"], f"{row['count']:,}"]
        for row in analysis["survey_counts"][:5]
    ]
    county_rows = [
        [row["name"], f"{row['count']:,}"]
        for row in analysis["county_counts"][:6]
    ]
    gender_rows = [
        [row["name"], f"{row['count']:,}"]
        for row in analysis["gender_counts"][:5]
        if row["name"] != "Unknown"
    ]
    age_rows = [
        [row["name"], f"{row['count']:,}"]
        for row in analysis["age_group_counts"][:6]
        if row["name"] != "Unknown"
    ]
    theme_rows = [
        [row["label"], f"{row['count']:,}", f"{row['share']}%"]
        for row in analysis["theme_overview"][:6]
    ]

    terms = analysis["top_terms"]
    top_county_names = ", ".join(row["name"] for row in analysis["county_counts"][:3])
    satisfaction_items = [item for item in analysis["satisfaction_counts"] if item["name"] != "Unknown"][:4]
    sentiment_items = analysis["sentiment_counts"][:3]
    county_chart_items = analysis["county_counts"][:5]
    theme_chart_items = analysis["theme_overview"][:6]

    flow = [
        Paragraph("CLM Feedback Analysis", styles["Kicker"]),
        Paragraph("HIV Care and Treatment Services: CLM Feedback Analysis", styles["ReportTitle"]),
        Paragraph(
            "This report summarizes patient and community feedback on HIV care and treatment services and focuses on service experience, access barriers, client satisfaction, and the main improvement priorities emerging from open-ended responses.",
            styles["Body"],
        ),
        Spacer(1, 0.35 * cm),
        stat_table(analysis["metrics"], styles),
        Spacer(1, 0.45 * cm),
        Paragraph("Background and Context", styles["SectionTitle"]),
        Paragraph(
            "This analysis is grounded in a community-led monitoring style of review, where patient and client voices are treated as a core source of evidence on how services are experienced at facility level. The framing is also consistent with the inception material, which emphasizes mixed methods, direct stakeholder voice, and reader-friendly presentation of charts, tables, and findings.",
            styles["Body"],
        ),
        Paragraph(
            "In Kenya, this work sits within a broader HIV response ecosystem that includes community networks such as NEPHAK, national and county health structures, and global HIV partners such as PEPFAR/USAID, UNAIDS, the Global Fund, WHO, and other implementing organizations working on prevention, treatment, retention, and community systems strengthening. The report itself stays focused on the survey evidence and what respondents said about service delivery.",
            styles["Body"],
        ),
        Paragraph("Overview", styles["SectionTitle"]),
        Paragraph(
            f"The analysis covers 23,457 responses, with the largest share coming from CLM feedback and the strongest county concentration in {top_county_names}. Overall satisfaction is high, but the comments also show clear operational concerns that should inform quality improvement and client support discussions.",
            styles["Body"],
        ),
        Paragraph(
            "Across the dataset, respondents most often praise friendly staff, respectful treatment, and good service delivery. The strongest recurring concerns relate to medicines and supplies, food and transport support, equipment and infrastructure, and waiting time.",
            styles["Body"],
        ),
        Paragraph("Survey Coverage", styles["SectionTitle"]),
        simple_table(
            ["Survey module", "Responses"],
            survey_rows,
            [11.6 * cm, 5 * cm],
        ),
        Spacer(1, 0.3 * cm),
        simple_table(
            ["County", "Responses"],
            county_rows,
            [11.6 * cm, 5 * cm],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph("Demographic Data", styles["SectionTitle"]),
        Table(
            [
                [
                    simple_table(["Gender", "Responses"], gender_rows, [6.8 * cm, 1.4 * cm]),
                    simple_table(["Age group", "Responses"], age_rows, [6.8 * cm, 1.4 * cm]),
                ]
            ],
            colWidths=[8.2 * cm, 8.2 * cm],
            hAlign="LEFT",
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
        ),
        Spacer(1, 0.3 * cm),
        Paragraph("Approach and Methodology", styles["SectionTitle"]),
        Paragraph(
            "1. The workbook was extracted and cleaned into a structured dataset with harmonized dates, counties, respondent fields, and service indicators.",
            styles["Body"],
        ),
        Paragraph(
            "2. Core service indicators were standardized, including satisfaction, access challenges, confidentiality, rights awareness, equipment adequacy, and counseling-related feedback.",
            styles["Body"],
        ),
        Paragraph(
            "3. Open-text responses on likes, dislikes, improvement requests, access barriers, and mental health concerns were reviewed using sentiment scoring and theme tagging.",
            styles["Body"],
        ),
        Paragraph(
            "4. Recurring issues were grouped into practical themes such as staff attitude, medicines and supplies, waiting time, access cost, equipment and infrastructure, confidentiality and stigma, and counseling or mental wellbeing.",
            styles["Body"],
        ),
        Paragraph(
            "5. Findings were then summarized into tables, comment excerpts, and simple text visuals that can be used directly during a meeting or presentation.",
            styles["Body"],
        ),
        PageBreak(),
        Paragraph("Accessibility to Health Care Services", styles["SectionTitle"]),
        simple_table(
            ["Priority theme", "Mentions", "Share of all responses"],
            theme_rows,
            [9.6 * cm, 3.2 * cm, 4 * cm],
        ),
        Spacer(1, 0.35 * cm),
        Paragraph(
            "The strongest positive signal in the feedback is relational quality. Respondents repeatedly describe friendly staff, respectful reception, caring providers, and timely service. These are important strengths to protect because they shape trust, continuity of care, and willingness to return to the facility.",
            styles["Body"],
        ),
        Paragraph(
            f"On the challenge side, the comments concentrate around {', '.join(item['term'] for item in terms['improvements'][:6])}. The narrative around dissatisfaction is less about staff interaction and more about practical bottlenecks that affect access, continuity, and perceived quality.",
            styles["Body"],
        ),
        Table(
            [
                [
                    pie_chart("Satisfaction mix", satisfaction_items),
                    pie_chart("Sentiment mix", sentiment_items),
                ]
            ],
            colWidths=[8.2 * cm, 8.2 * cm],
            hAlign="LEFT",
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
        ),
        Spacer(1, 0.25 * cm),
        vertical_bar_chart(
            "Top counties by response volume",
            [item["name"] for item in county_chart_items],
            [item["count"] for item in county_chart_items],
        ),
        Spacer(1, 0.25 * cm),
        Paragraph("Level of Satisfaction with Services", styles["SectionTitle"]),
        Paragraph(
            "Satisfaction levels are generally strong, and the sentiment mix is largely positive. Even so, the open comments show that high satisfaction scores can exist alongside recurring operational issues, particularly where medicines, transport support, supplies, and waiting time are involved.",
            styles["Body"],
        ),
        horizontal_bar_chart(
            "Most common themes in open comments",
            [item["label"] for item in theme_chart_items],
            [item["count"] for item in theme_chart_items],
        ),
        Spacer(1, 0.3 * cm),
        PageBreak(),
        Paragraph("What Clients Liked About the Facility", styles["SectionTitle"]),
        Paragraph(
            "The most common positive descriptions point to staff friendliness, good reception, respectful treatment, and supportive care. These comments suggest that interpersonal quality remains one of the strongest drivers of positive client experience in the facilities represented here.",
            styles["Body"],
        ),
        Table(
            [[WordCloudBlock("Positive language", terms["positive"]), WordCloudBlock("Improvement language", terms["improvements"])]],
            colWidths=[8.2 * cm, 8.2 * cm],
            hAlign="LEFT",
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
        ),
        Spacer(1, 0.3 * cm),
        Paragraph("What Needs to Be Improved", styles["SectionTitle"]),
        Paragraph(
            "The improvement responses show that clients are not only commenting on quality in the abstract; they are describing specific gaps that affect the care experience. The most repeated requests are more reliable medicines and supplies, stronger food and transport support, better equipment and infrastructure, and shorter waiting time.",
            styles["Body"],
        ),
        Paragraph("Challenges", styles["SectionTitle"]),
        Paragraph(
            "The comments point to a clear set of recurring barriers. Respondents want more reliable medicines and supplies, better food and transport support, improved equipment and infrastructure, and shorter waiting time. These are the issues most likely to reduce access and satisfaction if they persist.",
            styles["Body"],
        ),
        Paragraph(
            "A smaller but important part of the workbook focuses on mental health and community support. In that section, the language shifts toward counseling, psychosocial support, depression, anxiety, violence, and economic stress. This suggests that the same analysis workflow can also support broader community wellbeing reviews when needed.",
            styles["Body"],
        ),
        *quote_block("What Clients Appreciated", analysis["quotes"]["positive"], styles),
        *quote_block("What Clients Want Improved", analysis["quotes"]["improvement"], styles),
        Paragraph("Recommendations", styles["SectionTitle"]),
        Paragraph(
            "1. Maintain and reinforce the positive service culture already visible in the comments, especially respectful reception, friendliness, and client-centered care.",
            styles["Body"],
        ),
        Paragraph(
            "2. Prioritize operational fixes around medicines and supplies, transport and nutrition support, equipment, and waiting time because these issues appear repeatedly across improvement comments.",
            styles["Body"],
        ),
        Paragraph(
            "3. Review county and facility patterns regularly so that the same feedback can be used for targeted supervision, supportive coaching, and follow-up action on recurring service bottlenecks.",
            styles["Body"],
        ),
        Paragraph(
            "4. Continue pairing quantitative indicators with open comments during presentations and review meetings, because the narrative evidence helps explain why otherwise strong satisfaction scores may still coexist with specific access challenges.",
            styles["Body"],
        ),
    ]
    return flow


def main() -> None:
    analysis = load_analysis()
    styles = make_styles()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(REPORT_PATH),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Community Feedback and Service Experience Analysis Brief",
        author="OpenAI Codex",
    )
    doc.build(build_story(analysis, styles), onFirstPage=page_frame, onLaterPages=page_frame)

    APP_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPORT_PATH, APP_REPORT_PATH)
    print(f"Wrote {REPORT_PATH}")
    print(f"Copied report into {APP_REPORT_PATH}")


if __name__ == "__main__":
    main()
