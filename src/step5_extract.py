import os
import json
import PyPDF2
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Setup Mistral
client = OpenAI(
    api_key=os.getenv("MISTRAL_API_KEY"),
    base_url="https://api.mistral.ai/v1"
)

# Create folders
os.makedirs('extracted_data', exist_ok=True)
os.makedirs('processed', exist_ok=True)

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
            return text
    except Exception as e:
        print(f"   Error: {e}")
        return ""

def extract_invoice_data(text, filename):
    """Send to LLM to extract structured invoice data"""
    print("entered into llm extraction")
    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=[{
            "role": "user",
            "content": f"""Extract invoice data from this document. Return ONLY valid JSON.

Document:
{text[:4000]}

Return this exact structure:
{{
    "invoice_number": "string or null",
    "vendor_name": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "total_amount": number or null,
    "line_items": [
        {{
            "description": "string",
            "quantity": number,
            "unit_price": number
        }}
    ]
}}

If field missing, use null. If no line items, use empty array.
"""
        }],
        temperature=0
    )
    print("just before result")
    print(response)
    print(response.choices)
    print("we got choices")
    print(response.choices[0])
    print("we got choices")
    result = json.loads(response.choices[0].message.content)
    print("now we got the result")
    result['source_file'] = filename
    result['extracted_at'] = datetime.now().isoformat()
    return result

def main():
    invoice_folder = 'classified/invoices'
    
    if not os.path.exists(invoice_folder):
        print("❌ No invoices folder. Run step4 first.")
        return
    
    pdf_files = [f for f in os.listdir(invoice_folder) if f.endswith('.pdf')]
    
    if not pdf_files:
        print("📭 No PDFs in classified/invoices/")
        print("   Run step3 and step4 first to download and classify emails")
        return
    
    print(f"\n📑 Found {len(pdf_files)} invoice(s) to process\n")
    print("="*60)
    
    all_results = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(invoice_folder, pdf_file)
        print(f"\n📄 Processing: {pdf_file}")
        
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            print(f"   ❌ No text extracted - skipping")
            continue
        
        print(f"   📝 Extracted {len(text)} characters")
        
        # Extract data using LLM
        try:
            extracted = extract_invoice_data(text, pdf_file)
            
            # Save individual JSON
            json_path = f"extracted_data/{pdf_file.replace('.pdf', '.json')}"
            with open(json_path, 'w') as f:
                json.dump(extracted, f, indent=2)
            
            all_results.append(extracted)
            
            # Print summary
            print(f"   ✅ Invoice: {extracted.get('invoice_number', 'N/A')}")
            print(f"   🏢 Vendor: {extracted.get('vendor_name', 'N/A')}")
            print(f"   💰 Total: ${extracted.get('total_amount', 'N/A')}")
            print(f"   📅 Date: {extracted.get('invoice_date', 'N/A')}")
            print(f"   📦 Items: {len(extracted.get('line_items', []))}")
            print(f"   💾 Saved: {json_path}")
            
            # Move processed PDF to processed folder
            import shutil
            shutil.move(pdf_path, f"processed/{pdf_file}")
            
        except Exception as e:
            print(f"   ❌ Extraction failed: {e}")
    
    # Save master file
    if all_results:
        master_path = 'extracted_data/all_invoices.json'
        with open(master_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        print("\n" + "="*60)
        print("✅ EXTRACTION COMPLETE")
        print("="*60)
        print(f"📊 Processed: {len(all_results)} invoices")
        print(f"📁 Data saved: extracted_data/")
        print(f"📄 Master file: extracted_data/all_invoices.json")
        print(f"🗂️  Original PDFs: processed/")
        
        # Show sample
        if all_results:
            print("\n📋 Sample extracted data:")
            sample = all_results[0]
            print(f"   Invoice: {sample.get('invoice_number', 'N/A')}")
            print(f"   Vendor: {sample.get('vendor_name', 'N/A')}")
            print(f"   Total: ${sample.get('total_amount', 'N/A')}")
    else:
        print("\n❌ No invoices were successfully processed")

if __name__ == "__main__":
    main()