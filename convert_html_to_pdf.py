"""
Convert HTML 10-K files to PDF using weasyprint.
"""

import os
from pathlib import Path
from weasyprint import HTML


def convert_html_to_pdf(html_file: str, output_dir: str = "data") -> str:
    """
    Convert an HTML file to PDF.

    Args:
        html_file: Path to the HTML file
        output_dir: Directory to save the PDF (default: data/)

    Returns:
        Path to the generated PDF
    """
    if not os.path.exists(html_file):
        raise FileNotFoundError(f"HTML file not found: {html_file}")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create output filename
    base_name = Path(html_file).stem  # e.g., "AAPL_10k"
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

    print(f"Converting {html_file} to {pdf_path}...")

    try:
        HTML(filename=html_file).write_pdf(pdf_path)
        print(f"✓ PDF created successfully: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"✗ Error converting file: {e}")
        raise


if __name__ == "__main__":
    # Convert AAPL_10k.htm to PDF
    html_file = "data/AAPL_10k.htm"
    pdf_file = convert_html_to_pdf(html_file)
    print(f"\nPDF file size: {os.path.getsize(pdf_file) / 1024 / 1024:.2f} MB")
