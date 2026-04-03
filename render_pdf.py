"""
render_pdf.py
─────────────
Usage:
  python render_pdf.py                          # Japanese, output: report_ja.pdf
  python render_pdf.py --lang en                # English,  output: report_en.pdf
  python render_pdf.py --vars custom.json --out my_report.pdf

Dependencies:
  pip install weasyprint jinja2
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    sys.exit("ERROR: jinja2 is required. Run: pip install jinja2")

try:
    from weasyprint import HTML, CSS
except ImportError:
    sys.exit("ERROR: weasyprint is required. Run: pip install weasyprint")


TEMPLATE_FILE = "report_template.html"
VARS_MAP = {
    "ja": "variables_ja.json",
    "en": "variables_en.json",
}


def render(vars_path: Path, template_path: Path, output_path: Path) -> None:
    with vars_path.open(encoding="utf-8") as f:
        variables = json.load(f)

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    html_content = template.render(**variables)

    # Resolve base URL so relative paths (fonts, images) work
    base_url = template_path.parent.as_uri() + "/"

    print(f"Rendering PDF → {output_path} …")
    HTML(string=html_content, base_url=base_url).write_pdf(str(output_path))
    print(f"Done. {output_path.stat().st_size // 1024} KB written.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render report HTML → PDF via WeasyPrint")
    parser.add_argument("--lang", choices=["ja", "en"], default="ja",
                        help="Language preset (default: ja)")
    parser.add_argument("--vars", type=Path, default=None,
                        help="Path to custom variables JSON (overrides --lang)")
    parser.add_argument("--template", type=Path,
                        default=Path(__file__).parent / TEMPLATE_FILE)
    parser.add_argument("--out", type=Path, default=None,
                        help="Output PDF path (default: report_<lang>.pdf)")
    args = parser.parse_args()

    vars_path = args.vars or Path(__file__).parent / VARS_MAP[args.lang]
    output_path = args.out or Path(__file__).parent / f"report_{args.lang}.pdf"

    if not args.template.exists():
        sys.exit(f"ERROR: Template not found: {args.template}")
    if not vars_path.exists():
        sys.exit(f"ERROR: Variables file not found: {vars_path}")

    render(vars_path, args.template, output_path)


if __name__ == "__main__":
    main()
