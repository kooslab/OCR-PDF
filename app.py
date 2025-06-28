import streamlit as st
import anthropic
import fitz  # PyMuPDF
import pandas as pd
import io
import base64
from PIL import Image
import os
from dotenv import load_dotenv

# Load environment variables for local development
load_dotenv()

# Helper function to get config values
def get_config(key, default=None):
    # First try Streamlit secrets (for deployment)
    if hasattr(st, 'secrets') and key in st.secrets:
        return st.secrets[key]
    # Then try environment variables (for local development)
    return os.getenv(key, default)

st.set_page_config(page_title="PDF OCR with Claude", layout="wide")

def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if (
            st.session_state["username"] == get_config("AUTH_EMAIL", "admin@example.com")
            and st.session_state["password"] == get_config("AUTH_PASSWORD", "admin123")
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    with st.container():
        st.markdown("### 🔐 Login")
        st.text_input("Email", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("😕 User not known or password incorrect")
    return False

def pdf_to_images(pdf_file):
    """Convert PDF pages to images using PyMuPDF"""
    pdf_bytes = pdf_file.read()
    try:
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        # Convert each page to image
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            # Render page to image (2x scale for better quality)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.pil_tobytes(format="PNG")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        pdf_document.close()
        return images
    except Exception as e:
        st.error(f"Error converting PDF to images: {str(e)}")
        return None

def encode_image(image):
    """Encode PIL image to base64"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_text_with_claude(image, api_key, filename="", structured_format=None):
    """Use Claude to extract text from image"""
    client = anthropic.Anthropic(api_key=api_key)
    
    base64_image = encode_image(image)
    
    # Build the prompt based on whether we have a structured format
    if structured_format:
        prompt = f"""Please perform OCR on this image from file: {filename}

IMPORTANT: This appears to be a form or questionnaire with rating scales. Please extract the content in a consistent, structured format.

Expected format:
{structured_format}

Guidelines:
1. For rating scale questions (1-5), look for CIRCLED numbers (not X marks). Extract as: "Question text [Selected: X]" where X is the circled number
2. For multiple choice, show: "Question [Selected: Option]" 
3. For text fields, show: "Field name: [Content]"
4. Preserve the exact question numbers and order
5. If a question has sub-items (a, b, c), preserve that structure
6. If no option is circled/selected, indicate as [Selected: None]
7. IMPORTANT: Look for circles (○) around numbers, not checkmarks or X marks

Return the extracted content in a consistent, structured format that can be easily parsed."""
    else:
        prompt = f"""Please perform OCR on this image and extract all text content. 
    This is from file: {filename}
    
    Format the output as structured data if you identify:
    - Tables: preserve the table structure
    - Forms: extract field names and values
    - Lists: maintain list formatting
    - Rating scales: show as "Question [Selected: X]"
    
    Return the extracted text in a clear, organized format."""
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error processing image: {str(e)}"

def main():
    st.title("📄 Bulk PDF OCR with Claude")
    
    if not check_password():
        return
    
    st.markdown("---")
    
    api_key = st.text_input("Enter your Anthropic API Key:", type="password", value=get_config("ANTHROPIC_API_KEY", ""))
    
    if not api_key:
        st.warning("Please enter your Anthropic API key to continue")
        return
    
    # Add format template option
    with st.expander("📋 OCR Format Settings", expanded=False):
        st.info("Define a consistent format for structured documents (forms, questionnaires, etc.)")
        use_template = st.checkbox("Use structured format template")
        
        if use_template:
            format_template = st.text_area(
                "Format Template (customize based on your document type):",
                value="""Question 1: [Text field response]
Question 2: [Multiple sub-questions with 1-5 rating scale where users CIRCLE their choice]
  a) Sub-question text [Selected: (circled number 1-5)]
  b) Sub-question text [Selected: (circled number 1-5)]
  c) Sub-question text [Selected: (circled number 1-5)]
  ...
Question 3: [Multiple choice - Selected: Option]
Question 4: [Yes/No - Selected: Yes/No]

Note: Users circle numbers on rating scales, not mark with X""",
                height=200,
                help="This template helps Claude understand the expected structure of your documents"
            )
        else:
            format_template = None
    
    uploaded_files = st.file_uploader(
        "Upload PDF files (max 5)", 
        type=['pdf'], 
        accept_multiple_files=True,
        help="Upload up to 5 PDF files for OCR processing"
    )
    
    if uploaded_files and len(uploaded_files) > 5:
        st.error("Please upload maximum 5 files at a time")
        return
    
    if uploaded_files and st.button("🚀 Process PDFs", type="primary"):
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, pdf_file in enumerate(uploaded_files):
            status_text.text(f"Processing {pdf_file.name}...")
            progress_bar.progress((idx + 1) / len(uploaded_files))
            
            with st.expander(f"📄 {pdf_file.name}", expanded=True):
                pdf_file.seek(0)
                images = pdf_to_images(pdf_file)
                
                if images:
                    pdf_text = ""
                    cols = st.columns(2)
                    
                    for page_num, image in enumerate(images, 1):
                        with cols[0]:
                            st.markdown(f"**Page {page_num}**")
                            st.image(image, use_column_width=True)
                        
                        with cols[1]:
                            st.markdown(f"**Extracted Text - Page {page_num}**")
                            with st.spinner(f"Processing page {page_num}..."):
                                extracted_text = extract_text_with_claude(
                                    image, 
                                    api_key,
                                    f"{pdf_file.name} - Page {page_num}",
                                    structured_format=format_template
                                )
                                st.text_area(
                                    f"Text from page {page_num}", 
                                    extracted_text, 
                                    height=300,
                                    key=f"{pdf_file.name}_{page_num}"
                                )
                                pdf_text += f"\n\n--- Page {page_num} ---\n{extracted_text}"
                    
                    results.append({
                        "Filename": pdf_file.name,
                        "Pages": len(images),
                        "Extracted Text": pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text
                    })
        
        status_text.text("Processing complete!")
        progress_bar.progress(1.0)
        
        if results:
            st.markdown("## 📊 Summary Table")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download results as CSV",
                data=csv,
                file_name="ocr_results.csv",
                mime="text/csv"
            )
            
            st.markdown("## 📝 Full Extracted Texts")
            for idx, result in enumerate(results):
                with st.expander(f"{result['Filename']} - Full Text"):
                    full_text = next((r["Extracted Text"] for r in results if r["Filename"] == result["Filename"]), "")
                    st.text_area("Full text", full_text.replace("...", ""), height=400, key=f"full_{idx}")

if __name__ == "__main__":
    main()