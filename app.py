"""
Crochet Pattern PDF Generator — Web App
========================================
A beautiful web interface for generating crochet pattern PDFs using Gemini AI.

Run:  python app.py
Open: http://localhost:5000
"""

import os
import sys
import json
import time
import uuid
from flask import Flask, render_template, request, jsonify, send_file, redirect
from werkzeug.utils import secure_filename

# ─── Setup paths ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Import our generators ───
sys.path.insert(0, BASE_DIR)
from crochet_pdf_generator import generate_crochet_pdf
from ai_crochet_pdf import generate_pattern_with_ai, generate_images_for_pattern

# ─── Flask App ───
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.secret_key = 'crochet-pdf-secret-2026'

# ─── Access Codes (stored in file so they persist) ───
CODES_FILE = os.path.join(BASE_DIR, "access_codes.json")
ADMIN_PASSWORD = "admin2026crochet"  # Change this!

def _load_codes():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, 'r') as f:
            return set(json.load(f))
    return {"CROCHET2026", "PATTERN100", "YARNLOVE"}

def _save_codes(codes):
    with open(CODES_FILE, 'w') as f:
        json.dump(list(codes), f)

ACCESS_CODES = _load_codes()


@app.route('/')
def index():
    from flask import session
    if not session.get('authenticated'):
        return render_template('login.html')
    return render_template('index.html', saved_key='')


@app.route('/login', methods=['POST'])
def login():
    from flask import session
    code = request.form.get('code', '').strip().upper()
    if code in ACCESS_CODES:
        session['authenticated'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid access code"})


@app.route('/logout')
def logout():
    from flask import session
    session.pop('authenticated', None)
    return redirect('/')


@app.route('/admin')
def admin_page():
    from flask import session
    if not session.get('is_admin'):
        return render_template('admin_login.html')
    codes = _load_codes()
    return render_template('admin.html', codes=sorted(codes))


@app.route('/admin/login', methods=['POST'])
def admin_login():
    from flask import session
    password = request.form.get('password', '').strip()
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Wrong password"})


@app.route('/admin/add', methods=['POST'])
def admin_add_code():
    from flask import session
    if not session.get('is_admin'):
        return jsonify({"success": False, "error": "Not authorized"})
    code = request.form.get('code', '').strip().upper()
    if not code:
        return jsonify({"success": False, "error": "Code is empty"})
    global ACCESS_CODES
    ACCESS_CODES = _load_codes()
    ACCESS_CODES.add(code)
    _save_codes(ACCESS_CODES)
    return jsonify({"success": True, "codes": sorted(ACCESS_CODES)})


@app.route('/admin/delete', methods=['POST'])
def admin_delete_code():
    from flask import session
    if not session.get('is_admin'):
        return jsonify({"success": False, "error": "Not authorized"})
    code = request.form.get('code', '').strip().upper()
    global ACCESS_CODES
    ACCESS_CODES = _load_codes()
    ACCESS_CODES.discard(code)
    _save_codes(ACCESS_CODES)
    return jsonify({"success": True, "codes": sorted(ACCESS_CODES)})


@app.route('/prompts', methods=['POST'])
def get_prompts():
    """Generate image prompts for the pattern."""
    title = request.form.get('title', '').strip()
    if not title:
        return jsonify({"success": False, "error": "Title is required"})

    prompts = {
        "cover": f"Professional studio photo of a finished handmade crochet {title}, beautiful yarn craftsmanship, soft natural lighting, clean white background, product photography, high quality, no text no words",
        "materials": f"Aesthetic flat lay photography of crochet supplies for {title}: colorful yarn skeins, crochet hooks, stitch markers, scissors, neatly arranged on white marble surface, craft materials, no text no words",
        "steps": f"Close-up photo of hands crocheting {title}, crochet hook pulling yarn through stitches, work in progress on the lap, warm cozy lighting, crafting process detail, no text no words",
        "closing": f"Lifestyle photo of finished handmade crochet {title} in a beautiful home setting, styled on a cozy blanket or shelf, gift-ready, warm autumn aesthetic, no text no words",
    }
    return jsonify({"success": True, "prompts": prompts})


@app.route('/generate_text', methods=['POST'])
def generate_text():
    """Step 1: Generate pattern text only, return parts with image prompts."""
    try:
        api_key = request.form.get('api_key', '').strip()
        title = request.form.get('title', '').strip()
        provider = request.form.get('provider', 'gemini').strip()

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"})
        if not title:
            return jsonify({"success": False, "error": "Pattern title is required"})

        # Save reference image
        ref_path = None
        if 'reference' in request.files and request.files['reference'].filename:
            f = request.files['reference']
            ext = os.path.splitext(f.filename)[1] or '.jpg'
            ref_path = os.path.join(UPLOAD_DIR, f"ref_{uuid.uuid4().hex[:6]}{ext}")
            f.save(ref_path)
            print(f"[WEB] Reference image saved: {ref_path} ({os.path.getsize(ref_path)} bytes)")

        # ─── STEP 0: Analyze reference image colors INDEPENDENTLY ───
        detected_colors_raw = ""
        detected_colors_list = []
        if ref_path and os.path.exists(ref_path) and provider == "gemini":
            print(f"[WEB] Step 0: Analyzing reference image colors...")
            try:
                from google import genai as genai_client
                from google.genai import types as genai_types
                from PIL import Image as PILImage
                client = genai_client.Client(api_key=api_key)
                img = PILImage.open(ref_path).convert("RGB")
                # Resize for speed
                if max(img.size) > 800:
                    ratio = 800 / max(img.size)
                    img = img.resize((int(img.size[0]*ratio), int(img.size[1]*ratio)))

                color_resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[img, """Look at this image. What are the EXACT yarn/fabric colors you see?
Be very precise with color names. Examples: "baby pink", "dusty rose", "navy blue", "cream white", "sage green".
Reply ONLY in this format — nothing else:
COLORS: color1, color2, color3"""],
                    config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=100),
                )
                detected_colors_raw = color_resp.text.strip()
                print(f"[WEB] Colors detected: {detected_colors_raw}")

                # Parse "COLORS: baby pink, cream white" → ["baby pink", "cream white"]
                import re
                match = re.search(r'COLORS?:\s*(.+)', detected_colors_raw, re.IGNORECASE)
                if match:
                    detected_colors_list = [c.strip() for c in match.group(1).split(',') if c.strip()]
                print(f"[WEB] Parsed colors: {detected_colors_list}")
            except Exception as ce:
                print(f"[WEB] Color analysis failed: {ce}")

        # ─── STEP 1: Generate pattern with AI ───
        pattern_data = generate_pattern_with_ai(title, ref_path, api_key, provider=provider)

        # Truncate
        def _limit(text, max_words):
            words = text.split()
            return text if len(words) <= max_words else " ".join(words[:max_words]) + "..."
        pattern_data["about"] = _limit(pattern_data.get("about", ""), 55)
        pattern_data["before_you_begin"] = _limit(pattern_data.get("before_you_begin", ""), 45)
        for care in pattern_data.get("care_guide", []):
            care["desc"] = _limit(care.get("desc", ""), 18)

        # Save pattern data to temp file
        job_id = str(uuid.uuid4())[:8]
        data_path = os.path.join(OUTPUT_DIR, f"data_{job_id}.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(pattern_data, f, ensure_ascii=False)

        # ─── BUILD PROMPTS — USE DETECTED COLORS (not AI-generated ones) ───
        # Priority: detected_colors_list (from image) > yarn_colors (from AI JSON)
        if detected_colors_list:
            # USE REAL COLORS FROM IMAGE — this is the truth
            color_palette = ", ".join(detected_colors_list[:4])
            print(f"[WEB] Using IMAGE colors for prompts: {color_palette}")
        else:
            # Fallback to AI-generated colors
            yarn_colors = pattern_data.get("yarn_colors", [])
            exact_colors = [yc.get("color", "") for yc in yarn_colors if yc.get("color")]
            color_palette = ", ".join(exact_colors[:4]) if exact_colors else "pastel colored"
            print(f"[WEB] Using AI-generated colors for prompts: {color_palette}")

        # Also get product description for accurate prompts
        product_desc = pattern_data.get("about", title)
        finished_size = pattern_data.get("finished_size", "")

        # Image specs for PDF (9:16 portrait)
        IMG_SPEC = "square format 1:1 aspect ratio, high resolution 1440x1440"

        parts_prompts = []

        # Cover: finished product matching reference image exactly
        parts_prompts.append({
            "key": "cover",
            "name": "Cover — Finished Product",
            "prompt": f"Close-up photo of a finished handmade crochet {title}, made with {color_palette} yarn, {finished_size}, amigurumi style, beautiful yarn craftsmanship visible, soft natural lighting, clean white background, {IMG_SPEC}, no text no watermark no words",
        })

        # Per-part: hands-on crocheting process
        part_actions = {
            "head": "crocheting a round sphere shape, working in the round with single crochet stitches, crochet hook pulling yarn through loops",
            "body": "crocheting an oval body shape, increasing rounds visible, hook inserted into stitch pulling yarn through",
            "arm": "crocheting a small cylindrical tube shape, tiny piece on the hook, working single crochet in spiral rounds",
            "leg": "crocheting a small leg piece, working from the foot up, hook pulling through stitches on small cylinder",
            "ear": "crocheting a tiny flat circle ear piece, small delicate work on the hook, fingers holding tiny piece",
            "tail": "crocheting a small thin tail piece, working a chain or small tube, hook pulling yarn",
            "shell": "crocheting a dome shell shape, working increase rounds to form curved surface, hook through stitch",
            "fin": "crocheting a small flat fin piece, triangle shape forming on the hook",
            "wing": "crocheting a wing piece, flat fan shape, hook pulling through edge stitches",
            "beak": "crocheting a tiny cone beak, working decreases to form point, small piece on hook",
            "snout": "crocheting a small snout piece, oval shape forming, hook through front loops",
            "horn": "crocheting a cone horn shape, spiral decrease visible, hook pulling yarn through top",
            "mane": "crocheting loop stitches for mane texture, fingers pulling loops, fluffy yarn texture",
            "eye": "crocheting small circle patches for eyes, tiny flat rounds, contrasting yarn colors",
            "flower": "crocheting petals in a circle, chain loops forming flower shape, hook pulling through center ring",
            "leaf": "crocheting a pointed oval leaf, working increases and decreases, green yarn on hook",
            "strap": "crocheting a long flat strip handle, chain and single crochet rows, even tension visible",
            "pocket": "crocheting a flat square pocket piece, rows of single crochet, neat edges",
            "sole": "crocheting an oval sole shape, foundation chain with increases around, flat piece on hook",
            "cuff": "crocheting ribbed cuff texture, front post back post stitches, stretchy band forming",
            "panel": "crocheting a flat granny square panel, colorful rounds, hook pulling through chain spaces",
        }

        for i, part in enumerate(pattern_data.get("parts", [])):
            pname = part.get("name", f"Part {i+1}")

            # ALWAYS use detected colors from image if available
            if detected_colors_list:
                # Use the main detected color for all parts
                yarn_color = detected_colors_list[0]
                # If part has a specific different color (e.g. brim vs band), check others
                for dc in detected_colors_list:
                    if dc.lower() in part.get("color", "").lower():
                        yarn_color = dc
                        break
            else:
                # Fallback: try to extract from AI-generated color field
                color_field = part.get("color", "")
                import re
                color_match = re.search(r'[Uu]se\s+(.+?)\s+yarn', color_field)
                if color_match:
                    yarn_color = color_match.group(1)
                elif color_field:
                    yarn_color = color_field
                else:
                    yarn_color = color_palette

            # Match action by keyword
            action = "working single crochet stitches in the round, hook pulling yarn through loops, piece forming on the hook"
            for kw, act in part_actions.items():
                if kw in pname.lower():
                    action = act
                    break

            parts_prompts.append({
                "key": f"part_{i}",
                "name": f"{pname} — Work In Progress",
                "prompt": f"Close-up photo of hands crocheting the {pname.lower()} for a crochet {title}, {yarn_color} colored yarn, {action}, soft natural lighting, shallow depth of field, crochet hook clearly visible, {IMG_SPEC}, no text no watermark no words",
            })

        # Assembly: sewing pieces together with exact colors
        parts_prompts.append({
            "key": "assembly",
            "name": "Assembly — Sewing Together",
            "prompt": f"Close-up photo of hands sewing crochet {title} pieces together with a yarn needle, pieces made with {color_palette} yarn laid out on white table, assembly process, pins holding pieces, warm natural lighting, {IMG_SPEC}, no text no watermark no words",
        })

        # Closing: lifestyle finished product
        parts_prompts.append({
            "key": "closing",
            "name": "Closing — Lifestyle Photo",
            "prompt": f"Aesthetic lifestyle photo of finished handmade crochet {title}, made with {color_palette} yarn, displayed on a cozy knitted blanket, warm natural lighting, gift-ready styling, bokeh background, {IMG_SPEC}, no text no watermark no words",
        })

        # ─── Generate Etsy Listing Data ───
        skill = pattern_data.get("skill_level", "Intermediate")
        hook = pattern_data.get("hook_size", "")
        size = pattern_data.get("finished_size", "")
        total_time = pattern_data.get("total_time", "")
        parts_names = [p.get("name", "") for p in pattern_data.get("parts", [])]
        num_pages = 5 + len(pattern_data.get("parts", [])) // 3  # estimate

        # SEO Title (max 140 chars, max 3 words in ALL CAPS per Etsy rules)
        etsy_title_options = [
            f"Crochet Pattern PDF: {title} | Amigurumi Pattern | Instant Download | {skill} Level | Written Instructions with Photos",
            f"Crochet Pattern PDF: {title} | Amigurumi Pattern | Instant Download | {skill} Level | Step by Step",
            f"Crochet Pattern: {title} | Amigurumi PDF | Instant Download | {skill} | With Photos",
            f"Crochet Pattern: {title} | PDF Instant Download | Amigurumi | {skill}",
            f"Crochet Pattern: {title} | PDF Download | Amigurumi Pattern",
            f"{title} Crochet Pattern PDF | Instant Download",
        ]
        etsy_title = etsy_title_options[0]
        for opt in etsy_title_options:
            if len(opt) <= 140:
                etsy_title = opt
                break
        # Final safety trim
        if len(etsy_title) > 140:
            etsy_title = etsy_title[:137] + "..."

        # Etsy Description
        parts_list = ", ".join(parts_names[:6])
        etsy_description = f"""🧶 {title.upper()} — CROCHET PATTERN (PDF)

This is a DIGITAL CROCHET PATTERN (PDF file), NOT a finished product.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 WHAT YOU WILL RECEIVE:
• A beautifully designed {num_pages}+ page PDF pattern
• Clear, detailed written instructions in English
• Round-by-round instructions for each part
• Full materials list with exact quantities
• Assembly instructions with step-by-step guidance
• Helpful photos showing each stage of the process
• Abbreviation guide included
• Care instructions for your finished piece

📐 PATTERN DETAILS:
• Skill Level: {skill}
• Hook Size: {hook}
• Finished Size: {size}
• Estimated Time: {total_time}
• Language: English
• Format: PDF (Instant Download)

🧩 PATTERN INCLUDES PARTS:
{parts_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📥 HOW TO DOWNLOAD:
1. Purchase this listing
2. Go to "You" → "Purchases and reviews"
3. Click "Download Files" next to your order
4. Open the PDF on any device (phone, tablet, computer)
5. Print if desired — the pattern is yours forever!

⚠️ PLEASE NOTE:
• This is a DIGITAL DOWNLOAD — no physical item will be shipped
• The PDF will be available for download immediately after purchase
• Basic crochet knowledge is recommended
• Colors may vary depending on your yarn choice
• Pattern is for personal use only — do not redistribute

💬 NEED HELP?
If you have any questions about the pattern, feel free to message me! I'm happy to help you complete your project.

⭐ Don't forget to leave a review with a photo of your finished project — I'd love to see your creation!

Thank you for supporting handmade patterns! 🧶💕"""

        # Etsy Tags (max 13 tags, each max 20 chars)
        base = title.lower().replace("-", " ")
        words = base.split()
        etsy_tags = [
            "crochet pattern",
            "amigurumi pattern",
            "crochet pdf",
            "instant download",
            f"crochet {words[0]}" if words else "crochet toy",
            "amigurumi pdf",
            "crochet tutorial",
            "diy crochet",
            "handmade pattern",
            f"{words[-1]} pattern" if words else "toy pattern",
            "beginner crochet" if "beginner" in skill.lower() else "crochet gift",
            "digital pattern",
            "pdf pattern",
        ]
        # Trim each tag to 20 chars max
        etsy_tags = [t[:20] for t in etsy_tags]

        # ─── Pinterest SEO ───
        # Pinterest Title (max 100 chars, keyword-rich)
        pin_title_options = [
            f"Free Crochet Pattern: {title} | Step-by-Step PDF Tutorial with Photos",
            f"Crochet {title} Pattern | Easy PDF Tutorial | {skill} Level",
            f"How to Crochet {title} | Free Pattern PDF | {skill}",
            f"DIY Crochet {title} | Pattern PDF Tutorial",
            f"Crochet {title} | PDF Pattern",
        ]
        pin_title = pin_title_options[0]
        for opt in pin_title_options:
            if len(opt) <= 100:
                pin_title = opt
                break
        if len(pin_title) > 100:
            pin_title = pin_title[:97] + "..."

        # Pinterest Description (max 500 chars, keyword-rich, with hashtags)
        pin_description = f"""Learn how to crochet this adorable {title} with our detailed step-by-step PDF pattern! Perfect for {skill.lower()} level crocheters. This {num_pages}+ page pattern includes round-by-round instructions, full materials list, assembly guide, and helpful photos.

Hook: {hook} | Size: {size} | Time: {total_time}

Save this pin for your next crochet project!

#crochet #crochetpattern #amigurumi #crochettutorial #handmade #diy #crochetlove #yarn #crafts #maker #fiberart #crochetaddict #ravelry"""
        # Trim to 500 chars
        if len(pin_description) > 500:
            pin_description = pin_description[:497] + "..."

        # Pinterest Tags/Keywords
        pin_tags = [
            "crochet pattern",
            "amigurumi",
            "crochet tutorial",
            f"crochet {words[0]}" if words else "crochet toy",
            "handmade crochet",
            "diy crochet",
            "crochet ideas",
            "crochet for beginners" if "beginner" in skill.lower() else "crochet projects",
            "yarn crafts",
            f"{title.lower()}",
            "crochet pdf pattern",
            "free crochet pattern",
            "amigurumi pattern",
            "crochet gift ideas",
            "fiber arts",
        ]

        # Pinterest Board/Category suggestion
        pin_categories = [
            "Crochet Patterns & Tutorials",
            "Amigurumi & Stuffed Toys",
            "DIY & Crafts",
            "Yarn & Fiber Arts",
            "Handmade Gift Ideas",
        ]

        return jsonify({
            "success": True,
            "job_id": job_id,
            "title": title,
            "detected_colors": color_palette,
            "has_reference": ref_path is not None,
            "parts_count": len(pattern_data.get("parts", [])),
            "parts_prompts": parts_prompts,
            "etsy_title": etsy_title,
            "etsy_description": etsy_description,
            "etsy_tags": etsy_tags,
            "pin_title": pin_title,
            "pin_description": pin_description,
            "pin_tags": pin_tags,
            "pin_categories": pin_categories,
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/generate_pdf', methods=['POST'])
def generate_pdf_route():
    """Step 2: Generate PDF with uploaded images."""
    try:
        job_id = request.form.get('job_id', '').strip()
        if not job_id:
            return jsonify({"success": False, "error": "Missing job_id"})

        # Load pattern data
        data_path = os.path.join(OUTPUT_DIR, f"data_{job_id}.json")
        if not os.path.exists(data_path):
            return jsonify({"success": False, "error": "Pattern data not found. Generate text first."})

        with open(data_path, 'r', encoding='utf-8') as f:
            pattern_data = json.load(f)

        # Process uploaded images
        for key in request.files:
            file = request.files[key]
            if file.filename:
                ext = os.path.splitext(file.filename)[1] or '.jpg'
                img_path = os.path.join(UPLOAD_DIR, f"{job_id}_{key}{ext}")
                file.save(img_path)

                if key == "cover":
                    pattern_data["cover_image"] = img_path
                elif key == "closing":
                    pattern_data["closing_image"] = img_path
                elif key == "assembly":
                    pattern_data["assembly_image"] = img_path
                elif key.startswith("part_"):
                    idx = int(key.replace("part_", ""))
                    if idx < len(pattern_data.get("parts", [])):
                        pattern_data["parts"][idx]["image"] = img_path

        # Set defaults
        pattern_data.setdefault("cover_image", "")
        pattern_data.setdefault("closing_image", "")
        pattern_data.setdefault("steps_image", "")

        # Generate PDF — short filename for Etsy
        title = pattern_data.get("title", "Pattern")
        safe_title = "".join(c if c.isalnum() or c == " " else "" for c in title)
        short_name = "_".join(safe_title.split()[:3])
        filename = f"{short_name}_Pattern.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        generate_crochet_pdf(pattern_data, output_path)
        print(f"[WEB] PDF ready: {output_path}")

        return jsonify({"success": True, "filename": filename, "title": title})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/generate', methods=['POST'])
def generate():
    """Legacy: Handle PDF generation request (old workflow)."""
    try:
        api_key = request.form.get('api_key', '').strip()
        title = request.form.get('title', '').strip()
        provider = request.form.get('provider', 'gemini').strip()

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"})
        if not title:
            return jsonify({"success": False, "error": "Pattern title is required"})

        # Generate a unique ID for this job
        job_id = str(uuid.uuid4())[:8]

        # Save reference image (for AI analysis)
        ref_path = None
        if 'reference' in request.files and request.files['reference'].filename:
            f = request.files['reference']
            ext = os.path.splitext(f.filename)[1] or '.jpg'
            ref_path = os.path.join(UPLOAD_DIR, f"{job_id}_reference{ext}")
            f.save(ref_path)
            print(f"[WEB] Reference image saved: {ref_path}")

        # Save uploaded images
        cover_path = None
        materials_path = None
        steps_path = None
        closing_path = None

        for img_key in ['cover', 'materials', 'steps', 'closing']:
            if img_key in request.files and request.files[img_key].filename:
                f = request.files[img_key]
                ext = os.path.splitext(f.filename)[1] or '.jpg'
                path = os.path.join(UPLOAD_DIR, f"{job_id}_{img_key}{ext}")
                f.save(path)
                if img_key == 'cover': cover_path = path
                elif img_key == 'materials': materials_path = path
                elif img_key == 'steps': steps_path = path
                elif img_key == 'closing': closing_path = path

        # Step 1: Generate pattern with AI (pass reference image for analysis)
        print(f"\n[WEB] Generating pattern: \"{title}\" (job: {job_id})")
        pattern_data = generate_pattern_with_ai(title, ref_path or cover_path, api_key, provider=provider)

        # Step 1b: Truncate long text to prevent PDF overflow
        def _limit(text, max_words):
            words = text.split()
            if len(words) <= max_words:
                return text
            return " ".join(words[:max_words]) + "..."

        pattern_data["about"] = _limit(pattern_data.get("about", ""), 55)
        pattern_data["before_you_begin"] = _limit(pattern_data.get("before_you_begin", ""), 45)
        for care in pattern_data.get("care_guide", []):
            care["desc"] = _limit(care.get("desc", ""), 18)

        # Step 2: Add images (AI-generated if not uploaded)
        if not cover_path and not materials_path:
            print(f"[WEB] Generating AI images...")
            img_dir = os.path.join(BASE_DIR, "images")
            ai_images = generate_images_for_pattern(title, api_key, output_dir=img_dir)
            pattern_data["cover_image"] = ai_images.get("cover", "")
            pattern_data["materials_image"] = ai_images.get("materials", "")
            pattern_data["steps_image"] = ai_images.get("steps", "")
            pattern_data["closing_image"] = ai_images.get("closing", "")
        else:
            pattern_data["cover_image"] = cover_path or ""
            pattern_data["materials_image"] = materials_path or ""
            pattern_data["steps_image"] = steps_path or ""
            pattern_data["closing_image"] = closing_path or cover_path or ""
        pattern_data["steps_badge"] = "STEP BY STEP"
        pattern_data["variation_message"] = "Make it uniquely yours!"

        # Step 3: Generate PDF — short filename for Etsy
        safe_title = "".join(c if c.isalnum() or c == " " else "" for c in title)
        short_name = "_".join(safe_title.split()[:3])
        filename = f"{short_name}_Pattern.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        generate_crochet_pdf(pattern_data, output_path)

        print(f"[WEB] PDF ready: {output_path}")

        return jsonify({
            "success": True,
            "filename": filename,
            "title": title,
        })

    except Exception as e:
        print(f"[WEB] ERROR: {e}")
        import traceback
        traceback.print_exc()

        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            error_msg = "API rate limit reached. Please wait 1 minute and try again."
        elif "API key" in error_msg.lower() or "invalid" in error_msg.lower():
            error_msg = "Invalid API key. Please check your key and try again."

        return jsonify({"success": False, "error": error_msg})


@app.route('/download/<filename>')
def download(filename):
    """Download a generated PDF."""
    filepath = os.path.join(OUTPUT_DIR, secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return "File not found", 404


@app.errorhandler(Exception)
def handle_exception(e):
    """Catch ALL unhandled errors so server never crashes."""
    import traceback
    traceback.print_exc()
    return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


@app.errorhandler(500)
def handle_500(e):
    return jsonify({"success": False, "error": "Internal server error. Please try again."}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  CROCHET PATTERN PDF GENERATOR")
    print("  Web Interface Ready!")
    print("=" * 60)
    print(f"\n  Open in browser: http://localhost:5000")
    print(f"  Press Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
