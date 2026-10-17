import sys as _sys
import time as _time
from selenium.webdriver.support.ui import WebDriverWait


def configure_terminal_encoding():
    """
    Configures terminal stdout and stderr to UTF-8 to safely handle Unicode characters (₹, ★, etc.) on Windows.
    """
    if hasattr(_sys.stdout, 'reconfigure'):
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(_sys.stderr, 'reconfigure'):
        _sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def extract_product_urls(driver, timeout=15):
    """
    Extracts product URLs from the current Flipkart search results page.
    """

    # Wait until product links appear
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("""
            return [...document.querySelectorAll('a[href*="/p/"]')]
                .some(a => {
                    const u = new URL(a.href, location.href);
                    return u.pathname.includes("/p/");
                });
        """)
    )

    # Extract links directly from the browser DOM
    products = driver.execute_script(r"""
        const seen = new Set();

        return [...document.querySelectorAll('a[href*="/p/"]')]
            .map(a => {
                const url = new URL(a.href, location.href);
                const card = a.closest('[data-id]');

                const productId =
                    url.searchParams.get('pid') ||
                    card?.getAttribute('data-id') ||
                    null;

                const listingId =
                    url.searchParams.get('lid');

                // Reject non-product links
                if (!url.pathname.includes('/p/') || !productId) {
                    return null;
                }

                // Avoid duplicate product listings
                const key = productId + '|' + (listingId || '');

                if (seen.has(key)) {
                    return null;
                }

                seen.add(key);

                let title = (a.innerText || a.getAttribute('title') || '')
                    .replace(/\s+/g, ' ')
                    .trim();

                // If anchor text is missing or just price, retrieve card title
                if (!title || title.length < 3 || title.startsWith('₹') || title.includes('% off')) {
                    const cardTitle = card ? (card.querySelector('a.wjcEIp, a.WKTcLC, a[title], div.sylWjh, div.KzDlHZ, div._4rR01T, a.wByegH, a[class*="IRpwTa"], div[class*="title"], h2')?.innerText || '') : '';
                    if (cardTitle.trim().length > 3) title = cardTitle.trim().replace(/\s+/g, ' ');
                }

                const cardText = card ? card.innerText : a.innerText;
                const isOutOfStock = /out of stock|coming soon|currently unavailable/i.test(cardText);

                return {
                    title: title,
                    url: url.href,
                    product_id: productId,
                    listing_id: listingId,
                    in_stock: !isOutOfStock
                };
            })
            .filter(Boolean)
            .sort((a, b) => (b.in_stock ? 1 : 0) - (a.in_stock ? 1 : 0));
    """)

    return products




def extract_flipkart_product(driver, timeout=20):
    """
    Extracts product details from the current Flipkart product page.
    """
    # Wait for page load
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("""
                return document.readyState === 'complete' && document.body && document.body.innerText.length > 100;
            """)
        )
    except Exception as wait_err:
        print(f"[DEBUG] Page load wait notice: {wait_err}")


    # Scroll smoothly to load lazy sections
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
    _time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
    _time.sleep(1)

    # Click 'Specifications' tab or 'All details' if present to expand full specs
    try:
        driver.execute_script("""
            for (const el of document.querySelectorAll('button, div, span, a')) {
                const t = (el.innerText || '').trim();
                if ((t === 'Specifications' || t === 'All details') && el.children.length === 0) {
                    try { el.click(); } catch (e) {}
                }
            }
        """)
        _time.sleep(1)
    except Exception as e:
        print(f"[DEBUG] Spec accordion expansion notice: {e}")

    result = driver.execute_script(r"""
        const result = {
            selling_price: null,
            rating: null,
            listing_id: null,
            product_id: null,
            specifications: {}
        };

        // Extract listing_id and product_id from page if available
        try {
            const urlParams = new URLSearchParams(window.location.search);
            result.listing_id = urlParams.get('lid') || null;
            result.product_id = urlParams.get('pid') || null;

            if (!result.listing_id) {
                for (const el of document.querySelectorAll('button, a, input, form')) {
                    const href = el.getAttribute('href') || el.getAttribute('data-lid') || '';
                    if (href.includes('lid=')) {
                        const p = new URLSearchParams(href.split('?')[1] || href);
                        if (p.get('lid')) { result.listing_id = p.get('lid'); break; }
                    }
                }
            }
        } catch (e) {}

        // --------------------------------
        // 1. Helper: recursively traverse JSON
        // --------------------------------
        function walkJSON(obj, callback) {
            if (!obj || typeof obj !== 'object') return;
            callback(obj);
            if (Array.isArray(obj)) {
                for (const item of obj) { walkJSON(item, callback); }
            } else {
                for (const value of Object.values(obj)) { walkJSON(value, callback); }
            }
        }

        // --------------------------------
        // 2. Extract rating from JSON-LD
        // --------------------------------
        let productData = null;

        for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
                const data = JSON.parse(script.textContent);
                walkJSON(data, item => {
                    if (productData) return;
                    let types = item['@type'] || [];
                    if (typeof types === 'string') types = [types];
                    if (types.includes('Product')) productData = item;
                });
            } catch (error) {}
            if (productData) break;
        }

        if (productData) {
            const ratingData = productData.aggregateRating || {};
            if (ratingData.ratingValue != null) {
                result.rating = ratingData.ratingValue;
            }
        }

        // Fallback: DOM rating badge if JSON-LD didn't have it
        if (result.rating === null) {
            const ratingEl = document.querySelector('div.XQDdHH, div._3LWZlK, span[id*="productRating"], div[class*="XQDdHH"]');
            if (ratingEl) {
                const parsed = parseFloat(ratingEl.innerText);
                if (!isNaN(parsed) && parsed > 0 && parsed <= 5) {
                    result.rating = parsed;
                }
            }
        }

        // --------------------------------
        // 3. Extract current selling price
        // --------------------------------
        const leafElements = [...document.querySelectorAll('body *')]
            .filter(el => el.children.length === 0);

        const candidates = [];

        for (const el of leafElements) {
            const text = (el.innerText || '').trim();
            if (!/^₹\s*[\d,]+(?:\.\d+)?$/.test(text)) continue;

            const style = getComputedStyle(el);
            if (
                style.textDecorationLine.includes('line-through') ||
                style.textDecoration.includes('line-through')
            ) continue;

            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0 ||
                style.visibility === 'hidden' || style.display === 'none') continue;

            const price = Number(text.replace(/[₹,\s]/g, ''));
            if (!Number.isFinite(price)) continue;

            let node = el;
            let priceSection = false;
            for (let depth = 0; node && depth < 5; depth++) {
                const context = node.innerText || '';
                if (context.includes('Add to Cart') || context.includes('Buy Now')) {
                    priceSection = true;
                    break;
                }
                node = node.parentElement;
            }
            candidates.push({ price, priceSection });
        }

        const preferred = candidates.find(item => item.priceSection);
        if (preferred) {
            result.selling_price = preferred.price;
        } else if (candidates.length > 0) {
            result.selling_price = candidates[0].price;
        }

        // --------------------------------
        // 4. Extract Specifications
        // --------------------------------
        const specs = {};
        const BAD_KEYS = new Set([
            'b', 'u', 'y', 'buy now', 'buy with emi', 'add to cart', 'delivery',
            'cash on', 'flipkart', 'available offers', 'bank offers', 'reviews',
            'ratings', 'rating', 'special price', 'total', 'price', 'protect promise fee'
        ]);

        function isValidSpecPair(k, v) {
            if (!k || !v) return false;
            k = k.trim();
            v = v.trim();
            if (k.length < 2 || k.length > 70) return false;
            if (v.length < 1 || v.length > 300) return false;
            if (k.includes('\n')) return false;
            if (/^[₹$€£\d]/.test(k)) return false;
            if (BAD_KEYS.has(k.toLowerCase())) return false;
            if (k.toLowerCase().includes('buy with emi')) return false;
            if (k.toLowerCase().includes('pay with')) return false;
            if (v.includes('\n\n')) return false;
            return true;
        }

        // Approach A: Flipkart dynamic spec grid elements & column rows
        const gridElements = document.querySelectorAll('div.grid-formation-dynamic, div[class*="grid-column-2"], div.grid-formation');
        for (const el of gridElements) {
            const txt = (el.innerText || '').trim();
            const lines = txt.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            if (lines.length === 2 && isValidSpecPair(lines[0], lines[1])) {
                specs[lines[0]] = lines[1].replace(/\s+/g, ' ');
                continue;
            }

            // Child container scan (for flex / inline rows where text lacks newlines)
            const candidates = [el, ...el.querySelectorAll('div')];
            for (const c of candidates) {
                const textChildren = [...c.children].filter(child => (child.innerText || '').trim().length > 0);
                if (textChildren.length === 2 || textChildren.length === 3) {
                    const k = (textChildren[0].innerText || '').trim();
                    const v = (textChildren[1].innerText || '').trim();
                    if (isValidSpecPair(k, v)) {
                        specs[k] = v.replace(/\s+/g, ' ');
                        break;
                    }
                }
            }
        }

        // Approach B: Traditional HTML tables
        if (Object.keys(specs).length === 0) {
            for (const tr of document.querySelectorAll('tr')) {
                const cells = tr.querySelectorAll('td, th');
                if (cells.length === 2) {
                    const k = (cells[0].innerText || '').trim();
                    const v = (cells[1].innerText || '').trim();
                    if (isValidSpecPair(k, v)) {
                        specs[k] = v;
                    }
                }
            }
        }

        result.specifications = specs;
        return result;
    """)

    return result




def handle_cart_retry(driver, delay=2):
    """
    Checks for a temporary 'Retry' button or banner in Flipkart Cart and clicks it if detected.
    """
    try:
        retried = driver.execute_script("""
            for (const el of document.querySelectorAll('button, div, span, a')) {
                if ((el.innerText || '').trim().toLowerCase() === 'retry') {
                    el.click();
                    return true;
                }
            }
            return false;
        """)
        if retried:
            print("[INFO] Cart retry button was detected and clicked.")
            _time.sleep(delay)
            return True
        return False
    except Exception as retry_err:
        print(f"[DEBUG] Cart retry check: {retry_err}")
        return False




def add_to_cart_ui_fallback(driver):
    """
    Attempts to click 'Add to Cart' or 'Add to Basket' button directly via browser DOM.
    Useful for Grocery items, items requiring UI interactions, or when API request is unconfirmed.
    Returns True if an add button was clicked, False otherwise.
    """
    try:
        clicked = driver.execute_script("""
            for (const el of document.querySelectorAll('button, a, div[role="button"]')) {
                const text = (el.innerText || '').trim().toLowerCase();
                if (text === 'add to cart' || text === 'add to basket' || text.startsWith('add to cart') || text.startsWith('add to basket')) {
                    try { el.click(); return true; } catch(e) {}
                }
            }
            return false;
        """)
        if clicked:
            print("[INFO] Clicked 'Add to Cart / Basket' via browser UI fallback.")
            _time.sleep(3)
            return True
        return False
    except Exception as e:
        print(f"[DEBUG] UI add-to-cart fallback notice: {e}")
        return False




def extract_cart_total(driver, max_attempts=5, delay=1):
    """
    Extracts the payable Total Amount from the Flipkart Cart (/viewcart) page.
    """
    for attempt_no in range(1, max_attempts + 1):
        try:
            total_amount = driver.execute_script(r"""
                // Switch to Grocery tab if regular cart is empty and grocery tab has items
                for (const el of document.querySelectorAll('a, button, div[role="tab"]')) {
                    const txt = (el.innerText || '').trim().toLowerCase();
                    if (txt.includes('grocery') && !txt.includes('(0)')) {
                        try { el.click(); } catch(e) {}
                        break;
                    }
                }

                // 1. Locate element with text 'Total Amount' and inspect sibling/parent
                for (const el of document.querySelectorAll('*')) {
                    if ((el.innerText || '').trim() === 'Total Amount' && el.children.length === 0) {
                        const p = el.parentElement;
                        if (p) {
                            for (const c of p.children) {
                                if (c !== el) {
                                    const t = (c.innerText || '').trim();
                                    if (t.includes('₹') || /^[\d,]+$/.test(t)) {
                                        return t;
                                    }
                                }
                            }
                            const m = p.innerText.match(/₹\s*[\d,]+/);
                            if (m) return m[0];
                        }
                    }
                }

                // 2. Parse from Price Details text section
                const bodyText = document.body ? document.body.innerText : '';
                const match = bodyText.match(/Total Amount\s*\n?\s*(₹\s*[\d,]+)/);
                if (match) return match[1].trim();

                // 3. Fallback CSS selectors
                const candidate = document.querySelector('div.CTTtEa, div[class*="CTTtEa"], div._1dqVHU span, div.LAlFNR span, div.iqqSrT');
                if (candidate) {
                    const m = candidate.innerText.match(/Total Amount\s*\n?\s*(₹\s*[\d,]+)/);
                    if (m) return m[1].trim();
                }

                // 4. Bottom checkout bar next to 'Place Order'
                for (const b of document.querySelectorAll('button, a')) {
                    if ((b.innerText || '').trim().toLowerCase() === 'place order') {
                        const p = b.parentElement;
                        if (p) {
                            const m = p.innerText.match(/₹\s*[\d,]+/);
                            if (m) return m[0].trim();
                        }
                    }
                }

                return null;
            """)
            if total_amount:
                return total_amount
        except Exception as parse_err:
            print(f"[DEBUG] Cart total parsing attempt {attempt_no}/{max_attempts} failed: {parse_err}")
            
        if attempt_no < max_attempts:
            _time.sleep(delay)
            
    return None
