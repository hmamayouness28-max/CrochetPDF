"""
AI Crochet PDF Generator
=========================
Uses Google Gemini AI to automatically generate a full 8-page
crochet pattern PDF from just a title and images.

Setup:
    1. Get your API key from https://aistudio.google.com/apikey
    2. Set it below or as environment variable GEMINI_API_KEY
    3. Run: python ai_crochet_pdf.py

Usage:
    python ai_crochet_pdf.py --title "Amigurumi Cat" --cover cover.jpg --materials mat.jpg --closing close.jpg
    python ai_crochet_pdf.py   (interactive mode)
"""

import os
import sys
import json
import time
import argparse
from google import genai
from google.genai import types
from mistralai.client import Mistral
from PIL import Image

# ─── Import the PDF generator ───
from crochet_pdf_generator import generate_crochet_pdf

# ══════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════

# Put your Gemini API key here, or set GEMINI_API_KEY env variable
API_KEY = ""  # <-- Paste your key here if you want


def get_api_key():
    """Get API key from config, environment, or user input."""
    key = API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("\n" + "=" * 60)
        print("  GEMINI API KEY NEEDED")
        print("  Get yours at: https://aistudio.google.com/apikey")
        print("=" * 60)
        key = input("\nPaste your API key: ").strip()
    return key


# ══════════════════════════════════════════════════════════
# GEMINI AI PROMPT — This is the magic prompt
# ══════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an expert American crochet pattern designer writing professional patterns
for the US market (Ravelry, Etsy). You write PART-BY-PART, ROUND-BY-ROUND instructions
exactly like paid patterns sold on Ravelry.

CRITICAL RULES:
- US terminology ONLY: sc, dc, hdc, inc, dec, sl st, ch, MR, FLO, BLO
- US hook sizes: letter + metric (e.g. "E/4 (3.5mm)")
- Round-by-round format: "R1: MR of 6 sc [6]" with stitch count in brackets
- Each body part is a SEPARATE section with its own rounds
- Professional imperative voice: "6 inc [12]" not "you should increase"
- Stitch counts in brackets at end of each round: [6] [12] [18] [24]
- Be PRECISE — a crocheter must be able to follow without guessing"""

USER_PROMPT_TEMPLATE = """Create a complete crochet pattern for: "{title}"

{image_context}

Generate a FULL JSON response with this EXACT structure (no markdown, just raw JSON):

{{
    "title": "{title}",
    "subtitle": "1 sentence description",
    "badge": "SKILL LEVEL (e.g. INTERMEDIATE, BEGINNER FRIENDLY)",
    "total_time": "Time estimate",
    "skill_level": "Beginner or Intermediate or Advanced",
    "hook_size": "US hook (e.g. E/4 (3.5mm))",
    "yarn_weight": "US weight (e.g. 4-Worsted)",
    "finished_size": "Dimensions (e.g. 8 inches / 20cm tall)",

    "about": "Professional 2-sentence description of the finished item. Max 50 words.",

    "yarn_colors": [
        {{"name": "Main Color", "color": "exact descriptive color name (e.g. baby blue, dusty rose, sage green, cream white)", "usage": "head, body"}},
        {{"name": "Accent Color", "color": "exact descriptive color (e.g. soft pink, chocolate brown)", "usage": "details, cheeks"}}
    ],

    "materials": [
        "Yarn color 1 with EXACT color name, brand style and yardage",
        "Yarn color 2 with EXACT color name if needed",
        "Hook size",
        "Safety eyes with size",
        "Fiberfill stuffing",
        "Tapestry needle",
        "Stitch markers",
        "Scissors"
    ],

    "abbreviations": [
        {{"short": "MR", "full": "Magic Ring"}},
        {{"short": "sc", "full": "Single Crochet"}},
        {{"short": "inc", "full": "Increase (2 sc in same st)"}},
        {{"short": "dec", "full": "Invisible Decrease"}},
        {{"short": "sl st", "full": "Slip Stitch"}},
        {{"short": "ch", "full": "Chain"}},
        {{"short": "FLO", "full": "Front Loop Only"}},
        {{"short": "BLO", "full": "Back Loop Only"}}
    ],

    "before_you_begin": "Important notes: continuous rounds vs joined, stuffing tips, etc. Max 40 words.",
    "gauge": "Gauge measurement (e.g. 5 sc x 6 rows = 1 inch with E/4 hook)",

    "parts": [
        {{
            "name": "Head",
            "color": "Use baby blue yarn (or exact color from image)",
            "rounds": [
                "R1: MR of 6 sc [6]",
                "R2: 6 inc [12]",
                "R3: (1 sc, inc) x6 [18]",
                "R4: (2 sc, inc) x6 [24]",
                "R5: (3 sc, inc) x6 [30]",
                "R6-R10: 30 sc [30]",
                "R11: (3 sc, dec) x6 [24]",
                "R12: (2 sc, dec) x6 [18]",
                "Insert safety eyes between R8-R9, 6 st apart",
                "Stuff firmly",
                "R13: (1 sc, dec) x6 [12]",
                "R14: 6 dec [6]",
                "Fasten off, close hole"
            ],
            "note": "Stuff firmly before closing. Pull magic ring tight."
        }},
        {{
            "name": "Body",
            "color": "Use baby blue yarn (or exact color from image)",
            "rounds": [
                "R1: MR of 6 sc [6]",
                "R2: 6 inc [12]",
                "R3: (1 sc, inc) x6 [18]",
                "R4: (2 sc, inc) x6 [24]",
                "R5-R10: 24 sc [24]",
                "R11: (2 sc, dec) x6 [18]",
                "Stuff firmly",
                "R12: (1 sc, dec) x6 [12]",
                "Leave long tail for sewing"
            ],
            "note": "Do not close — leave open for attaching to head."
        }}
    ],

    "assembly": [
        "Sew the head to the body, centering it on top. Use mattress stitch for invisible seam.",
        "Attach arms to sides of body at R3-R4, evenly spaced.",
        "Sew legs to bottom of body.",
        "Weave in all ends securely."
    ],

    "finishing": [
        "Embroider nose/mouth with black yarn using straight stitches.",
        "Add blush to cheeks with pink yarn or fabric marker.",
        "Adjust stuffing and shape as needed."
    ],

    "care_guide": [
        {{"title": "Wash", "desc": "Hand wash gently in cool water with mild soap."}},
        {{"title": "Dry", "desc": "Squeeze out water, reshape, air dry flat."}},
        {{"title": "Store", "desc": "Keep in a dry, dust-free place."}}
    ],

    "quick_reference": {{
        "hook": "Hook size",
        "yarn": "Yarn type",
        "size": "Finished size",
        "key_stitch": "Main stitch"
    }},

    "thank_you_message": "Thank you message. Max 20 words.",
    "footer": "CROCHET PATTERN - PERSONAL USE ONLY"
}}

CRITICAL REQUIREMENTS:
- Generate 4-8 PARTS depending on the project (Head, Body, Arms, Legs, Tail, Shell, etc.)
- Each part MUST have 5-15 rounds of REAL round-by-round instructions
- Each round line must end with stitch count in brackets: [6] [12] [18] [24] [30] [36]
- Include notes for stuffing, color changes, markers between rounds
- Generate 3-5 assembly steps
- Generate 2-3 finishing steps
- Generate 8 abbreviations relevant to this pattern
- The rounds must be MATHEMATICALLY CORRECT:
  * Starting MR of 6: [6] -> inc all: [12] -> (1sc,inc)x6: [18] -> (2sc,inc)x6: [24] etc.
  * Decreases: (3sc,dec)x6: [24] -> (2sc,dec)x6: [18] -> (1sc,dec)x6: [12] -> 6dec: [6]
- Return ONLY valid JSON, no markdown, no explanation
- This must read like a REAL $5+ Ravelry pattern

COLOR MATCHING — VERY IMPORTANT:
- If an image is provided, analyze the EXACT COLORS visible in the photo
- Use precise descriptive color names (NOT generic): "baby blue", "dusty rose", "sage green", "cream white", "charcoal gray", "soft lavender", "burnt orange", "forest green", "powder pink"
- Each part's "color" field MUST specify the exact yarn color: "Use dusty rose yarn" NOT "Use main color"
- "yarn_colors" array MUST list every distinct color visible with exact descriptive names
- Materials list MUST include exact color names: "Dusty Rose worsted weight yarn, 120 yards" NOT "Main color yarn"
- If NO image provided, choose realistic harmonious colors that match the project type"""


# ══════════════════════════════════════════════════════════
# AI GENERATION — SHARED HELPERS
# ══════════════════════════════════════════════════════════

def _parse_ai_response(raw_text):
    """Clean and parse AI JSON response."""
    import re
    raw_text = raw_text.strip()
    # Remove markdown code blocks
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        clean_lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(clean_lines)
    # Extract JSON block
    try:
        start = raw_text.index("{")
        end = raw_text.rindex("}") + 1
        raw_text = raw_text[start:end]
    except ValueError:
        pass
    # Fix trailing commas (common AI mistake): ,} or ,]
    raw_text = re.sub(r',\s*}', '}', raw_text)
    raw_text = re.sub(r',\s*]', ']', raw_text)
    return json.loads(raw_text)


# ══════════════════════════════════════════════════════════
# AI IMAGE GENERATION (Gemini)
# ══════════════════════════════════════════════════════════

def generate_images_for_pattern(title, api_key, output_dir="images"):
    """
    Generate 4 contextual images for a crochet pattern PDF using Gemini.
    Returns dict of image paths: {cover, materials, steps, closing}.
    Gracefully returns empty paths if image generation fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c == " " else "" for c in title).replace(" ", "_")

    image_prompts = {
        "cover": f"Professional studio photo of a finished handmade crochet {title}, beautiful craftsmanship, soft lighting, clean background, product photography style, no text",
        "materials": f"Flat lay photography of crochet materials for making {title}: colorful yarn skeins, crochet hooks, stitch markers, scissors, arranged neatly on white surface, craft supplies, no text",
        "steps": f"Close-up photo of hands crocheting {title} in progress, showing crochet hook working yarn stitches, work in progress, crafting process, warm lighting, no text",
        "closing": f"Lifestyle photo of finished crochet {title} in a cozy home setting, styled product photo, warm aesthetic, gift-ready handmade item, no text",
    }

    results = {}
    client = genai.Client(api_key=api_key)

    for key, prompt in image_prompts.items():
        img_path = os.path.join(output_dir, f"{safe_title}_{key}.png")
        results[key] = ""  # default empty

        try:
            print(f"[IMG] Generating {key} image...")
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image"):
                    with open(img_path, "wb") as f:
                        f.write(part.inline_data.data)
                    results[key] = img_path
                    print(f"[IMG] {key} image saved: {img_path}")
                    break
        except Exception as e:
            print(f"[IMG] {key} image failed (will use placeholder): {str(e)[:80]}")

        # Small delay between requests
        time.sleep(2)

    return results


# ══════════════════════════════════════════════════════════
# MISTRAL AI GENERATION
# ══════════════════════════════════════════════════════════

def _generate_with_mistral(title, api_key, image_context=""):
    """Generate pattern using Mistral AI."""
    client = Mistral(api_key=api_key)
    prompt_text = USER_PROMPT_TEMPLATE.format(title=title, image_context=image_context)

    models_to_try = [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
    ]

    last_error = None
    for model_name in models_to_try:
        print(f"[MISTRAL] Trying model: {model_name}...")
        try:
            response = client.chat.complete(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.7,
                max_tokens=8000,
            )
            raw_text = response.choices[0].message.content
            pattern_data = _parse_ai_response(raw_text)

            print(f"[MISTRAL] Pattern generated successfully with {model_name}!")
            print(f"     Title: {pattern_data.get('title')}")
            print(f"     Steps: {len(pattern_data.get('steps', []))}")
            print(f"     Materials: {len(pattern_data.get('materials', []))}")
            return pattern_data

        except Exception as e:
            last_error = str(e)
            print(f"[WARN] {model_name} failed: {last_error[:120]}")
            if "429" in last_error or "rate" in last_error.lower():
                time.sleep(3)
            continue

    error_msg = f"Mistral AI failed. Last error: {str(last_error)[:150]}"
    raise Exception(error_msg)


# ══════════════════════════════════════════════════════════
# GEMINI AI GENERATION
# ══════════════════════════════════════════════════════════

def _generate_with_gemini(title, api_key, cover_image=None):
    """Generate pattern using Google Gemini AI."""
    client = genai.Client(api_key=api_key)

    image_context = ""
    content_parts = []
    color_analysis = ""

    if cover_image and os.path.exists(cover_image):
        try:
            img = Image.open(cover_image).convert("RGB")
            max_dim = 1024
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)

            # STEP 0: Quick color analysis from the image FIRST
            print("[GEMINI] Step 0: Analyzing reference image colors...")
            try:
                color_response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[img, "Look at this crochet/yarn product image. List ONLY the exact yarn colors you see. Be very specific with color names (e.g. 'baby pink' not 'pink', 'cream white' not 'white'). Reply in this format ONLY:\nCOLORS: color1, color2, color3\nPRODUCT: brief description of what the product is"],
                    config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=200),
                )
                color_analysis = color_response.text.strip()
                print(f"[GEMINI] Color analysis: {color_analysis}")
            except Exception as ce:
                print(f"[GEMINI] Color pre-analysis failed: {ce}")
                color_analysis = ""

            content_parts.append(img)

            image_context = f"""I've attached a REFERENCE IMAGE of the exact product to recreate.

IMAGE COLOR ANALYSIS RESULT: {color_analysis}

YOU MUST USE THE EXACT COLORS FROM THE IMAGE ABOVE.
DO NOT INVENT OR GUESS COLORS. The colors you see in the image are the ONLY colors to use.
- If the image shows baby pink yarn → every "color" field must say "baby pink"
- If the image shows cream white → use "cream white"
- NEVER use colors that are NOT visible in the reference image
- The yarn_colors array MUST match the image analysis above EXACTLY
- Each part's "color" field MUST say "Use [exact color from image] yarn"
- Materials list MUST use these exact color names"""

        except Exception as e:
            print(f"[AI] Could not load image: {e}")
            image_context = "No image provided. Generate the pattern based on the title alone."
    else:
        image_context = "No image provided. Choose realistic harmonious colors that match the project type."

    prompt_text = USER_PROMPT_TEMPLATE.format(title=title, image_context=image_context)
    content_parts.append(prompt_text)

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]

    last_error = None
    for model_name in models_to_try:
        print(f"[GEMINI] Trying model: {model_name}...")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=8000,
                ),
            )
            raw_text = response.text.strip()
            pattern_data = _parse_ai_response(raw_text)

            print(f"[GEMINI] Pattern generated successfully with {model_name}!")
            print(f"     Title: {pattern_data.get('title')}")
            print(f"     Steps: {len(pattern_data.get('steps', []))}")
            print(f"     Materials: {len(pattern_data.get('materials', []))}")
            return pattern_data

        except Exception as e:
            last_error = str(e)
            print(f"[WARN] {model_name} failed: {last_error[:100]}")
            if "429" in last_error or "503" in last_error or "quota" in last_error.lower():
                time.sleep(3)
            continue

    error_msg = "All Gemini models unavailable. "
    if "429" in str(last_error) or "quota" in str(last_error).lower():
        error_msg += "API quota exceeded — wait 1 minute."
    elif "503" in str(last_error):
        error_msg += "High demand — try again in 30 seconds."
    else:
        error_msg += f"Last error: {str(last_error)[:150]}"
    raise Exception(error_msg)


# ══════════════════════════════════════════════════════════
# MAIN AI DISPATCHER
# ══════════════════════════════════════════════════════════

def generate_pattern_with_ai(title, cover_image=None, api_key=None, provider="gemini"):
    """
    Generate crochet pattern data using AI.

    Args:
        title: Name of the crochet project
        cover_image: Optional path to an image for context
        api_key: API key for the chosen provider
        provider: "gemini" or "mistral"

    Returns:
        dict: Complete pattern data ready for PDF generation
    """
    if not api_key:
        api_key = get_api_key()

    print(f"[AI] Generating pattern for: \"{title}\" using {provider.upper()}...")

    if provider == "mistral":
        return _generate_with_mistral(title, api_key)
    else:
        return _generate_with_gemini(title, api_key, cover_image)


# ══════════════════════════════════════════════════════════
# MAIN — FULL PIPELINE
# ══════════════════════════════════════════════════════════

def create_crochet_pdf(title, cover_image=None, materials_image=None,
                       closing_image=None, output_name=None, api_key=None):
    """
    Full pipeline: AI generates content -> PDF is created.

    Args:
        title: Crochet project name
        cover_image: Path to cover image
        materials_image: Path to materials image
        closing_image: Path to closing page image
        output_name: Output PDF filename (auto-generated if None)
        api_key: Gemini API key
    """
    print("\n" + "=" * 60)
    print("  CROCHET PATTERN PDF GENERATOR")
    print("  Powered by Google Gemini AI")
    print("=" * 60)

    # Step 1: Generate pattern with AI
    print(f"\n--- STEP 1: AI Content Generation ---")
    pattern_data = generate_pattern_with_ai(title, cover_image, api_key)

    # Step 1b: Truncate any overly long text to prevent PDF overflow
    def _limit(text, max_words):
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    pattern_data["about"] = _limit(pattern_data.get("about", ""), 55)
    pattern_data["before_you_begin"] = _limit(pattern_data.get("before_you_begin", ""), 45)
    # Parts rounds are kept as-is (they're short round lines)
    for care in pattern_data.get("care_guide", []):
        care["desc"] = _limit(care.get("desc", ""), 18)

    # Step 2: Generate AI images (if no user images provided)
    print(f"\n--- STEP 2: Adding Images ---")
    if not cover_image and not materials_image:
        print("[IMG] No user images — generating AI images...")
        img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
        ai_images = generate_images_for_pattern(title, api_key, output_dir=img_dir)
        pattern_data["cover_image"] = ai_images.get("cover", "")
        pattern_data["materials_image"] = ai_images.get("materials", "")
        pattern_data["steps_image"] = ai_images.get("steps", "")
        pattern_data["closing_image"] = ai_images.get("closing", "")
    else:
        pattern_data["cover_image"] = cover_image or ""
        pattern_data["materials_image"] = materials_image or ""
        pattern_data["steps_image"] = ""
        pattern_data["closing_image"] = closing_image or cover_image or ""

    pattern_data["steps_badge"] = "STEP BY STEP"
    pattern_data["variation_message"] = "Make it uniquely yours!"

    # Step 3: Generate PDF
    print(f"\n--- STEP 3: Generating PDF ---")
    if not output_name:
        safe_title = "".join(c if c.isalnum() or c == " " else "" for c in title)
        output_name = safe_title.replace(" ", "_") + "_Pattern.pdf"

    output_path = generate_crochet_pdf(pattern_data, output_name)

    print("\n" + "=" * 60)
    print(f"  DONE! Your PDF is ready:")
    print(f"  {os.path.abspath(output_path)}")
    print("=" * 60 + "\n")

    return output_path


def interactive_mode():
    """Interactive mode - ask the user for inputs."""
    print("\n" + "=" * 60)
    print("  CROCHET PATTERN PDF GENERATOR")
    print("  Powered by Google Gemini AI")
    print("=" * 60)

    # Get API key
    api_key = get_api_key()

    # Get title
    print("\n--- What crochet pattern do you want to create? ---")
    print("Examples:")
    print("  - Amigurumi Teddy Bear")
    print("  - Granny Square Blanket")
    print("  - Baby Booties Set")
    print("  - Crochet Market Bag")
    print("  - Sunflower Coaster Set")
    title = input("\nPattern title: ").strip()
    if not title:
        print("No title provided. Exiting.")
        return

    # Get images
    print("\n--- Images (press Enter to skip any) ---")
    cover = input("Cover image path: ").strip().strip('"').strip("'")
    materials = input("Materials image path: ").strip().strip('"').strip("'")
    closing = input("Closing image path (or Enter to reuse cover): ").strip().strip('"').strip("'")

    if not cover or not os.path.exists(cover):
        cover = None
        print("  (No cover image - will use dark background)")
    if not materials or not os.path.exists(materials):
        materials = None
    if not closing or not os.path.exists(closing):
        closing = cover

    # Generate!
    create_crochet_pdf(
        title=title,
        cover_image=cover,
        materials_image=materials,
        closing_image=closing,
        api_key=api_key,
    )


# ══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Crochet Pattern PDF Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ai_crochet_pdf.py
      (Interactive mode - asks you for everything)

  python ai_crochet_pdf.py --title "Amigurumi Cat"
      (Generate with just a title, no images)

  python ai_crochet_pdf.py --title "Baby Blanket" --cover baby.jpg
      (Generate with title + cover image)

  python ai_crochet_pdf.py --title "Market Bag" --cover bag.jpg --materials yarn.jpg --closing bag2.jpg
      (Full generation with all images)

  python ai_crochet_pdf.py --title "Cozy Scarf" --key YOUR_API_KEY
      (Provide API key directly)
        """
    )

    parser.add_argument("--title", "-t", help="Crochet pattern title")
    parser.add_argument("--cover", "-c", help="Cover image path")
    parser.add_argument("--materials", "-m", help="Materials image path")
    parser.add_argument("--closing", help="Closing page image path")
    parser.add_argument("--output", "-o", help="Output PDF filename")
    parser.add_argument("--key", "-k", help="Gemini API key")

    args = parser.parse_args()

    if args.title:
        # CLI mode
        create_crochet_pdf(
            title=args.title,
            cover_image=args.cover,
            materials_image=args.materials,
            closing_image=args.closing or args.cover,
            output_name=args.output,
            api_key=args.key,
        )
    else:
        # Interactive mode
        interactive_mode()
