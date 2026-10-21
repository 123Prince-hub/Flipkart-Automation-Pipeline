import sys
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def configure_terminal_encoding():
    """
    Configures terminal stdout and stderr to UTF-8 to safely handle Unicode characters (₹, ★, etc.) on Windows.
    """
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


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


    # Scroll smoothly to load page elements
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
    time.sleep(1)

    result = driver.execute_script(r"""
        const result = {
            selling_price: null,
            rating: null,
            listing_id: null,
            product_id: null
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
            const offers = productData.offers || {};
            const op = Array.isArray(offers) ? offers[0]?.price : offers.price;
            if (op && Number(op) > 0) {
                result.selling_price = Number(op);
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
        if (!result.selling_price) {
            const primaryPriceEl = document.querySelector('div.Nx9bqj.CxhGGd, div._30jeq3._16Jk6d, div.Nx9bqj');
            if (primaryPriceEl) {
                const num = Number(primaryPriceEl.innerText.replace(/[₹,\s]/g, ''));
                if (Number.isFinite(num) && num > 0) {
                    result.selling_price = num;
                }
            }
        }

        if (!result.selling_price) {
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
        }

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
            time.sleep(delay)
            return True
        return False
    except Exception as retry_err:
        print(f"[DEBUG] Cart retry check: {retry_err}")
        return False


def clean_numeric_price(val):
    """
    Parses any numeric price representation (int, float, string like '₹ 15,000') into an integer.
    Returns 0 if parsing fails.
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    try:
        clean = str(val).replace("₹", "").replace(",", "").strip()
        if not clean:
            return 0
        return int(float(clean))
    except (ValueError, TypeError):
        return 0


def create_worker_driver(worker_id=1, headless=False):
    """
    Creates an isolated Selenium Chrome WebDriver instance for a specific thread/worker.
    Ensures independent user-data and session cookies per worker.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    else:
        # Cascade windows with desktop viewport so full UI elements render
        window_width = 1100
        window_height = 850
        x_pos = (worker_id - 1) * 280
        y_pos = (worker_id - 1) * 50
        options.add_argument(f"--window-size={window_width},{window_height}")
        options.add_argument(f"--window-position={x_pos},{y_pos}")

    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Block images for speed and lower memory usage
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    return driver


def verify_http_session(driver, target_url, timeout=15):
    """
    Task 2: Extracts cookies from the Selenium browser session, creates an isolated
    requests.Session(), transfers the cookies, makes a request to a public endpoint,
    and records the HTTP status code.
    """
    session = requests.Session()
    try:
        browser_cookies = driver.get_cookies()
        for c in browser_cookies:
            session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain", ".flipkart.com"),
                path=c.get("path", "/")
            )

        user_agent = driver.execute_script("return navigator.userAgent") or "Mozilla/5.0"
        headers = {
            "User-Agent": user_agent + " FKUA/website/42/website/Desktop",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.flipkart.com/"
        }

        req_url = target_url if (target_url and target_url.startswith("http")) else "https://www.flipkart.com"
        response = session.get(req_url, headers=headers, timeout=timeout, allow_redirects=True)
        return response.status_code
    except requests.RequestException:
        try:
            fb = session.get("https://www.flipkart.com", timeout=8)
            return fb.status_code
        except Exception:
            return 0
    finally:
        session.close()


def add_to_cart_selenium(driver, selected_product=None, product_details=None):
    """
    Task 3: Attempts to add the selected product to the cart using Selenium UI interaction,
    with cookie/Rome API synchronization to ensure cart session reliability.
    """
    selected_product = selected_product or {}
    product_details = product_details or {}

    # 1. Attempt Selenium UI button click
    ui_success = False
    try:
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(1)

        ui_success = driver.execute_script("""
            for (const el of document.querySelectorAll('button, a, div[role="button"]')) {
                const text = (el.innerText || '').trim().toLowerCase();
                if (text === 'add to cart' || text === 'add to basket' || text.startsWith('add to cart') || text.startsWith('add to basket')) {
                    try { 
                        el.scrollIntoView({behavior: 'instant', block: 'center'});
                        el.click(); 
                        return true; 
                    } catch(e) {}
                }
            }
            return false;
        """)
        if ui_success:
            time.sleep(2)
    except Exception:
        ui_success = False

    # 2. Rome API synchronization fallback
    listing_id = selected_product.get("listing_id") or product_details.get("listing_id")
    product_id = selected_product.get("product_id") or product_details.get("product_id")
    selling_price = clean_numeric_price(product_details.get("selling_price"))

    if listing_id and product_id:
        try:
            browser_cookies = driver.get_cookies()
            session = requests.Session()
            for cookie in browser_cookies:
                session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain"), path=cookie.get("path", "/"))

            payload = {
                "cartContext": {
                    listing_id: {
                        "productId": product_id,
                        "quantity": 1,
                        "cashifyDiscountApplied": False,
                        "vulcanDiscountApplied": False,
                        "payWithEMISelected": False,
                        "selectedActions": ["ADD_TO_CART"],
                        "primaryProductPrice": selling_price
                    }
                },
                "pageType": "ProductPage"
            }

            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": "https://www.flipkart.com",
                "Referer": driver.current_url,
                "X-User-Agent": driver.execute_script("return navigator.userAgent") + " FKUA/website/42/website/Desktop"
            }

            api_url = "https://1.rome.api.flipkart.com/api/5/cart"
            resp = session.post(api_url, headers=headers, json=payload, timeout=20)
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass

            if resp.status_code == 406 or data.get("ERROR_CODE") == 2000 or data.get("STATUS_CODE") == 406:
                dc_id = data.get("RESPONSE", {}).get("id")
                if dc_id:
                    api_url = f"https://{dc_id}.rome.api.flipkart.com/api/5/cart"
                    resp = session.post(api_url, headers=headers, json=payload, timeout=20)

            for c in session.cookies:
                try:
                    driver.add_cookie({"name": c.name, "value": c.value, "domain": ".flipkart.com", "path": "/"})
                except Exception:
                    try:
                        driver.add_cookie({"name": c.name, "value": c.value})
                    except Exception:
                        pass
            session.close()
            return True
        except Exception:
            pass

    return ui_success


def extract_cart_details(driver, expected_name="", expected_price=0, max_attempts=5):
    """
    Task 3: Verifies whether the selected product actually appears in the shopping cart.
    Extracts actual quantity, cart price, and verifies product match.
    Returns: dict(verified=bool, cart_price=int, quantity=int, name_matched=bool)
    """
    for attempt in range(1, max_attempts + 1):
        try:
            handle_cart_retry(driver)

            result = driver.execute_script(r"""
                const expectedName = (arguments[0] || '').toLowerCase();
                const expectedPrice = arguments[1] || 0;
                let text = document.body ? document.body.innerText : '';

                // Switch to Grocery tab only if regular cart is empty and a grocery tab with count exists
                if (text.includes("Missing Cart items?") || text.includes("Your cart is empty!")) {
                    for (const el of document.querySelectorAll('a, button, div[role="tab"]')) {
                        const txt = (el.innerText || '').trim().toLowerCase();
                        if (txt.includes('grocery (') && !txt.includes('(0)')) {
                            try { el.click(); } catch(e) {}
                            break;
                        }
                    }
                    text = document.body ? document.body.innerText : '';
                }

                if (text.includes("Missing Cart items?") && text.includes("Your cart is empty!")) {
                    return { verified: false, cart_price: 0, quantity: 0, reason: "CART_EMPTY" };
                }

                // 1. Extract Quantity
                let quantity = 1;
                const qtyMatch = text.match(/Qty:\s*(\d+)/i) || text.match(/Quantity:\s*(\d+)/i);
                if (qtyMatch) {
                    quantity = parseInt(qtyMatch[1], 10);
                } else {
                    const qtyInput = document.querySelector('input[type="text"][value], input.w6q99W');
                    if (qtyInput) {
                        const parsed = parseInt(qtyInput.value, 10);
                        if (!isNaN(parsed) && parsed > 0) quantity = parsed;
                    }
                }

                // 2. Extract item price from cart
                let cartPrice = 0;
                if (expectedPrice > 0) {
                    const priceFormatted = expectedPrice.toLocaleString('en-IN');
                    if (text.includes('₹' + expectedPrice) || text.includes('₹ ' + expectedPrice) ||
                        text.includes('₹' + priceFormatted) || text.includes('₹ ' + priceFormatted)) {
                        cartPrice = expectedPrice;
                    }
                }

                if (!cartPrice) {
                    const allMatches = [...text.matchAll(/₹\s*([\d,]+)/g)]
                        .map(m => parseInt(m[1].replace(/,/g, ''), 10))
                        .filter(p => !isNaN(p) && p > 0);
                    
                    if (allMatches.length > 0) {
                        if (expectedPrice > 0 && allMatches.includes(expectedPrice)) {
                            cartPrice = expectedPrice;
                        } else {
                            cartPrice = allMatches[0];
                        }
                    }
                }

                // 3. Extract payable Cart Total
                let cartTotal = 0;
                for (const el of document.querySelectorAll('*')) {
                    if ((el.innerText || '').trim() === 'Total Amount' && el.children.length === 0) {
                        const p = el.parentElement;
                        if (p) {
                            const m = p.innerText.match(/₹\s*([\d,]+)/);
                            if (m) {
                                cartTotal = parseInt(m[1].replace(/,/g, ''), 10);
                                break;
                            }
                        }
                    }
                }
                if (!cartTotal) {
                    const totalMatch = text.match(/Total Amount\s*\n?\s*₹\s*([\d,]+)/i);
                    if (totalMatch) cartTotal = parseInt(totalMatch[1].replace(/,/g, ''), 10);
                }
                if (!cartTotal) {
                    for (const b of document.querySelectorAll('button, a')) {
                        if ((b.innerText || '').trim().toLowerCase() === 'place order') {
                            const p = b.parentElement;
                            if (p) {
                                const m = p.innerText.match(/₹\s*([\d,]+)/);
                                if (m) { cartTotal = parseInt(m[1].replace(/,/g, ''), 10); break; }
                            }
                        }
                    }
                }
                if (!cartTotal) {
                    cartTotal = cartPrice;
                }

                // 4. Check product name presence
                let nameMatched = false;
                if (expectedName) {
                    const words = expectedName.replace(/[^a-z0-9\s]/g, ' ')
                        .split(/\s+/)
                        .filter(w => w.length > 3);
                    
                    const textLower = text.toLowerCase();
                    let hits = 0;
                    for (const w of words) {
                        if (textLower.includes(w)) hits++;
                    }
                    if (words.length > 0 && (hits / words.length) >= 0.20) {
                        nameMatched = true;
                    }
                }

                const hasCartContent = text.includes("Place Order") || text.includes("Total Amount") || text.includes("Save for later") || text.includes("Buy this now") || text.includes("Remove");
                const verified = (nameMatched || hasCartContent) && cartPrice > 0 && quantity > 0;

                return {
                    verified: verified,
                    cart_price: cartPrice,
                    cart_total: cartTotal,
                    quantity: quantity,
                    name_matched: nameMatched
                };
            """, expected_name, expected_price)

            if result and result.get("verified"):
                return result

        except Exception:
            pass

        time.sleep(1)

    return {"verified": False, "cart_price": 0, "cart_total": 0, "quantity": 0, "reason": "VERIFICATION_TIMEOUT"}

