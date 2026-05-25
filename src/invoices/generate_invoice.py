# generate_invoices.py
from fpdf import FPDF
from datetime import datetime

invoices = [
    {"vendor": "ABC Supplies", "number": "INV-001", "amount": 1249.99, "date": "2026-05-20", "line_items": "Office chairs (2) @ $624.99"},
    {"vendor": "TechDistro Inc", "number": "TD-2026-042", "amount": 4999.00, "date": "2026-05-22", "line_items": 'Laptop (1) @ $4999.00'},
    {"vendor": "FastLogistics", "number": "FL-8902", "amount": 750.50, "date": "2026-05-24", "line_items": "Shipping services"}
]

for inv in invoices:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="INVOICE", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Invoice #: {inv['number']}", ln=True)
    pdf.cell(200, 10, txt=f"Vendor: {inv['vendor']}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {inv['date']}", ln=True)
    pdf.cell(200, 10, txt=f"Total: ${inv['amount']}", ln=True)
    pdf.cell(200, 10, txt=f"Items: {inv['line_items']}", ln=True)
    pdf.output(f"{inv['number']}.pdf")
    print(f"Created: {inv['number']}.pdf")