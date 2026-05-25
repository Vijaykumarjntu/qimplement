import os
import PyPDF2
from openai import OpenAI

# Load OpenAI (we'll use for uncertain cases)
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# ====================== MISTRAL CLIENT SETUP ======================
mistral_key = os.getenv("MISTRAL_API_KEY")

if not mistral_key:
    print("❌ MISTRAL_API_KEY not found!")
    print("Please set it using:")
    print('   $env:MISTRAL_API_KEY = "your-mistral-key-here"')
    exit(1)

print("✅ Mistral API Key loaded successfully!")

client = OpenAI(
    api_key=mistral_key,
    base_url="https://api.mistral.ai/v1"     # ← Changed to Mistral
)

def extract_text_from_pdf(pdf_path):
    """Extract first page text for classification"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            # First 2 pages should be enough to classify
            for i in range(min(2, len(reader.pages))):
                text += reader.pages[i].extract_text()
            return text[:2000]  # First 2000 chars is enough
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return ""

def rule_based_classify(text):
    """Fast, free classification using keywords"""
    if not text:
        return "UNKNOWN", "No text extracted"
    
    text_lower = text.lower()
    
    # Invoice indicators
    invoice_keywords = [
        'invoice', 'bill to', 'ship to', 'invoice number', 'invoice no',
        'po number', 'purchase order', 'order number', 'due date',
        'payment terms', 'total amount', 'subtotal', 'tax', 'vendor'
    ]
    
    # Non-invoice indicators (books, resumes, etc)
    non_invoice_keywords = [
        'curriculum vitae', 'cv', 'resume', 'objective', 'work experience',
        'education', 'chapter', 'exercise', 'table of contents',
        'candidate', 'job application'
    ]
    
    invoice_score = sum(1 for kw in invoice_keywords if kw in text_lower)
    non_invoice_score = sum(1 for kw in non_invoice_keywords if kw in text_lower)
    
    if invoice_score >= 2:
        return "INVOICE", f"Found {invoice_score} invoice keywords"
    elif non_invoice_score >= 2:
        return "NOT_INVOICE", f"Found {non_invoice_score} non-invoice keywords"
    else:
        return "UNCERTAIN", f"Invoice score: {invoice_score}, Non-invoice: {non_invoice_score}"

def llm_classify(text):
    """More accurate, costs ~$0.001 per call"""
    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=[{
            "role": "user",
            "content": f"""Classify this document as INVOICE or NOT_INVOICE.
            
Rules:
- INVOICE: Contains vendor name, customer name, invoice number, line items, total amount
- NOT_INVOICE: Resume, book chapter, article, receipt without vendor details, personal document

Document text (first 2000 chars):
{text}

Respond with ONLY JSON: {{"classification": "INVOICE" or "NOT_INVOICE", "confidence": 0.0-1.0, "reason": "one sentence"}}
"""
        }],
        response_format={"type": "json_object"}
    )
    
    import json
    result = json.loads(response.choices[0].message.content)
    return result['classification'], result

def classify_pdfs():
    """Main function to classify all PDFs in inbox_pdfs/"""
    
    pdf_folder = 'inbox_pdfs'
    if not os.path.exists(pdf_folder):
        print("❌ No inbox_pdfs folder found")
        return
    
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    print(f"📄 Found {len(pdf_files)} PDFs to classify\n")
    
    results = {
        'invoice': [],
        'not_invoice': [],
        'uncertain': []
    }
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        print(f"🔍 Classifying: {pdf_file}")
        
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            print(f"   ⚠️ No text extracted\n")
            results['uncertain'].append((pdf_file, "No text extracted"))
            continue
        
        # Step 1: Rule-based
        rule_result, rule_reason = rule_based_classify(text)
        print(f"   📊 Rule-based: {rule_result} - {rule_reason}")
        
        # Step 2: If uncertain, use LLM
        if rule_result == "UNCERTAIN":
            print(f"   🤖 Using LLM for deeper analysis...")
            llm_result, llm_details = llm_classify(text)
            print(f"   🧠 LLM says: {llm_result} (confidence: {llm_details.get('confidence', 0)}")
            print(f"   💬 Reason: {llm_details.get('reason', 'N/A')}")
            
            final_result = llm_result
        else:
            final_result = rule_result
        
        # Store result
        if final_result == "INVOICE":
            results['invoice'].append(pdf_file)
            print(f"   ✅ Moving to PROCESS queue\n")
        elif final_result == "NOT_INVOICE":
            results['not_invoice'].append(pdf_file)
            print(f"   ❌ Moving to IGNORE queue\n")
        else:
            results['uncertain'].append((pdf_file, "Needs manual review"))
            print(f"   ⚠️ Moving to MANUAL_REVIEW queue\n")
    
    # Summary
    print("\n" + "="*50)
    print("CLASSIFICATION SUMMARY")
    print("="*50)
    print(f"✅ INVOICES to process: {len(results['invoice'])}")
    for f in results['invoice']:
        print(f"   - {f}")
    
    print(f"\n❌ NOT INVOICES to ignore: {len(results['not_invoice'])}")
    for f in results['not_invoice']:
        print(f"   - {f}")
    
    print(f"\n⚠️  UNCERTAIN (manual review): {len(results['uncertain'])}")
    for f, reason in results['uncertain']:
        print(f"   - {f} ({reason})")
    
    return results

if __name__ == "__main__":
    # Test with your PDFs
    classify_pdfs()