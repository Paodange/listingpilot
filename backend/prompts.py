"""
Platform-specific prompt templates for listing generation.
Each function returns a system prompt + user prompt pair.
"""

TONE_DESCRIPTIONS = {
    "professional": "Professional, confident, and authoritative. Focus on quality and reliability.",
    "friendly": "Warm, conversational, and approachable. Like a helpful friend recommending a product.",
    "luxury": "Elegant, refined, and aspirational. Emphasize premium quality and exclusivity.",
    "technical": "Precise, spec-focused, and detailed. Appeal to informed buyers who value data.",
}


def get_system_prompt() -> str:
    return (
        "You are an expert e-commerce copywriter who specializes in creating "
        "high-converting product listings. You understand SEO, buyer psychology, "
        "and the specific formatting requirements of each e-commerce platform. "
        "Always respond in valid JSON format with no markdown fencing."
    )


def build_amazon_prompt(product_name: str, features: str, audience: str, tone: str) -> str:
    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])
    return f"""Create an Amazon product listing for the following product.

Product: {product_name}
Key Features: {features}
Target Audience: {audience or "General consumers"}
Tone: {tone_desc}

Respond in this exact JSON structure:
{{
  "title": "An SEO-optimized Amazon title under 200 characters. Include brand, product name, key features, size/quantity, and primary benefit.",
  "bullets": [
    "Bullet 1 - lead with a benefit, support with feature. Use an emoji at the start. Under 500 characters.",
    "Bullet 2",
    "Bullet 3",
    "Bullet 4",
    "Bullet 5"
  ],
  "description": "A compelling product description of 150-300 words. Include keywords naturally. Focus on benefits and use cases."
}}

Requirements:
- Title must be under 200 characters
- Exactly 5 bullet points, each under 500 characters
- Bullet points start with an emoji and a CAPS benefit phrase
- Description should be keyword-rich but natural
- Follow Amazon's style guidelines"""


def build_shopify_prompt(product_name: str, features: str, audience: str, tone: str) -> str:
    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])
    return f"""Create a Shopify product page listing for the following product.

Product: {product_name}
Key Features: {features}
Target Audience: {audience or "General consumers"}
Tone: {tone_desc}

Respond in this exact JSON structure:
{{
  "title": "A clean, branded product title for Shopify storefront.",
  "description": "A well-structured product description with line breaks. Use short paragraphs. Include a checklist of key benefits using ✓ marks. 150-250 words.",
  "seo": {{
    "metaTitle": "SEO meta title under 60 characters including brand.",
    "metaDesc": "SEO meta description under 155 characters. Include primary keyword and a call to action."
  }}
}}

Requirements:
- Title should be clean and branded (not keyword-stuffed like Amazon)
- Description uses short paragraphs and benefit checkmarks
- Include SEO meta title and description
- Write for a DTC brand storefront audience"""


def build_etsy_prompt(product_name: str, features: str, audience: str, tone: str) -> str:
    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])
    return f"""Create an Etsy product listing for the following product.

Product: {product_name}
Key Features: {features}
Target Audience: {audience or "General consumers"}
Tone: {tone_desc}

Respond in this exact JSON structure:
{{
  "title": "An Etsy-optimized title with relevant long-tail keywords separated by bullet dots (•) or pipes (|). Under 140 characters.",
  "description": "A detailed Etsy description with sections separated by decorative dividers (━━━). Include: WHAT'S INCLUDED, WHY YOU'LL LOVE IT, PERFECT AS A GIFT, CARE INSTRUCTIONS sections. Use ✦ for section headers. 200-400 words. Warm and personal tone.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7"]
}}

Requirements:
- Title uses Etsy-style keyword separators (• or |)
- Description has decorative formatting with ━━━ dividers
- Include 7 relevant Etsy search tags (2-3 word phrases)
- Tone should feel handmade/artisanal even for manufactured products
- End with a personal thank-you note with emoji"""


def build_ebay_prompt(product_name: str, features: str, audience: str, tone: str) -> str:
    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])
    return f"""Create an eBay product listing for the following product.

Product: {product_name}
Key Features: {features}
Target Audience: {audience or "General consumers"}
Tone: {tone_desc}

Respond in this exact JSON structure:
{{
  "title": "An eBay title under 80 characters. Include key specs, condition (NEW), and important keywords. Use abbreviations like w/ for 'with'.",
  "description": "An eBay-style description with bold section headers using ▬▬▬ dividers. Include: product overview, sizes/specs, features list, condition, shipping info, and return policy. 150-250 words. Direct and informative.",
  "itemSpecifics": {{
    "Material": "value",
    "Type": "value",
    "Features": "value"
  }}
}}

Requirements:
- Title is concise with key specs (eBay has 80 char limit)
- Description uses ▬▬▬ dividers between sections
- Include 3-6 item specifics as key-value pairs
- Mention shipping and returns in description
- Style should be direct and transactional"""


PLATFORM_PROMPT_BUILDERS = {
    "amazon": build_amazon_prompt,
    "shopify": build_shopify_prompt,
    "etsy": build_etsy_prompt,
    "ebay": build_ebay_prompt,
}
