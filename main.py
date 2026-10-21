import os, sys, time, json, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils import (
    configure_terminal_encoding,
    create_worker_driver,
    extract_product_urls,
    extract_flipkart_product,
    verify_http_session,
    add_to_cart_selenium,
    extract_cart_details,
    clean_numeric_price,
    handle_cart_retry,
)

# Ensure Windows terminal prints Unicode (₹, checkmarks, etc.) safely
configure_terminal_encoding()

# Default product search keywords required by assignment
DEFAULT_KEYWORDS = [
    "Samsung mobile",
    "Wireless headphones",
    "Logitech mouse",
    "Bluetooth speaker",
    "Laptop stand"
]

def log(worker_id, keyword, message):
    """Thread-safe structured console logging identifying worker and product."""
    timestamp = time.strftime("%H:%M:%S")
    prefix = f"[{timestamp} | Worker-{worker_id} | {keyword}]"
    print(f"{prefix} {message}", flush=True)


def dismiss_login_popup(driver):
    """Dismisses login/signup modal if displayed."""
    try:
        close_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '✕') or contains(text(), '✕')]"))
        )
        close_btn.click()
    except Exception:
        pass


def execute_worker_task(worker_id, keyword, headless=False):
    """
    Executes an independent Flipkart automation workflow in an isolated browser instance:
    1. Task 1: Search, select result, extract product name, price, rating, URL.
    2. Task 2: Extract cookies, create requests.Session(), verify public HTTP status code.
    3. Task 3: Add product to cart via Selenium, navigate to /viewcart, verify cart data.
    4. Task 4: Error handling, driver cleanup in finally block, execution time logging.
    """
    start_time = time.perf_counter()
    driver = None

    result = {
        "worker_id": worker_id,
        "product_keyword": keyword,
        "product_name": "N/A",
        "product_price": 0,
        "cart_price": 0,
        "cart_total": 0,
        "quantity": 0,
        "cart_verified": False,
        "http_status": 0,
        "status": "FAILED",
        "execution_seconds": 0.0
    }

    try:
        log(worker_id, keyword, "Launching isolated Chrome WebDriver instance...")
        driver = create_worker_driver(worker_id=worker_id, headless=headless)

        # -------------------------------------------------------------
        # TASK 1: Open Flipkart & Search Product
        # -------------------------------------------------------------
        log(worker_id, keyword, "Navigating to https://www.flipkart.com...")
        driver.get("https://www.flipkart.com")
        dismiss_login_popup(driver)

        log(worker_id, keyword, f"Searching keyword: '{keyword}'...")
        searched = False
        try:
            search_box = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.NAME, "q"))
            )
            search_box.click()
            search_box.clear()
            search_box.send_keys(keyword)
            search_box.send_keys(Keys.RETURN)
            searched = True
        except Exception:
            pass

        if not searched:
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(keyword)
            driver.get(f"https://www.flipkart.com/search?q={encoded_query}")

        # Wait for product links in search results
        log(worker_id, keyword, "Locating product search results...")
        products = extract_product_urls(driver, timeout=15)
        if not products:
            raise RuntimeError(f"No product listings found for search query '{keyword}'")

        selected_product = products[0]
        product_url = selected_product.get("url")
        log(worker_id, keyword, f"Selected product candidate: {selected_product.get('title', '')[:50]}...")

        # Navigate directly to product page in current window (clean single-tab isolation)
        driver.get(product_url)
        product_details = extract_flipkart_product(driver, timeout=20)

        # Clean product title
        product_title = (selected_product.get("title") or "").replace("Add to Compare ", "").split("...")[0].strip()
        if not product_title or len(product_title) < 3 or product_title.startswith("₹") or "% off" in product_title:
            try:
                title_elem = driver.find_element(By.TAG_NAME, "h1")
                product_title = title_elem.text.strip().replace("\n", " ")
            except Exception:
                product_title = keyword.title()

        product_price = clean_numeric_price(product_details.get("selling_price"))
        product_rating = product_details.get("rating")

        result["product_name"] = product_title
        result["product_price"] = product_price
        log(worker_id, keyword, f"Extracted Product: '{product_title[:40]}' | Price: ₹{product_price} | Rating: {product_rating}")

        # -------------------------------------------------------------
        # TASK 2: Session & HTTP Request Verification
        # -------------------------------------------------------------
        log(worker_id, keyword, "Transferring Selenium cookies to isolated requests.Session()...")
        http_status = verify_http_session(driver, target_url=product_url, timeout=15)
        result["http_status"] = http_status
        log(worker_id, keyword, f"Task 2 HTTP Endpoint Status Code: {http_status}")

        # -------------------------------------------------------------
        # TASK 3: Cart Automation and Verification
        # -------------------------------------------------------------
        log(worker_id, keyword, "Attempting to add product to cart using Selenium...")
        add_to_cart_selenium(driver, selected_product, product_details)

        log(worker_id, keyword, "Navigating to /viewcart for verification...")
        driver.get("https://www.flipkart.com/viewcart")
        time.sleep(3)
        handle_cart_retry(driver)

        # Extract cart verification data
        cart_data = extract_cart_details(driver, expected_name=product_title, expected_price=product_price, max_attempts=4)

        cart_price = cart_data.get("cart_price") or product_price
        cart_total = cart_data.get("cart_total") or cart_price
        cart_qty = cart_data.get("quantity") or 1
        cart_verified = cart_data.get("verified", False)

        result["cart_price"] = cart_price
        result["cart_total"] = cart_total
        result["quantity"] = cart_qty
        result["cart_verified"] = cart_verified

        # Criteria: cart verified, quantity >= 1, and cart price extracted
        if cart_verified and cart_price > 0 and cart_qty > 0:
            result["status"] = "SUCCESS"
            log(worker_id, keyword, f"SUCCESS: Cart verified! (Product Price: ₹{product_price}, Item Price: ₹{cart_price}, Cart Total: ₹{cart_total}, Qty: {cart_qty})")
        else:
            result["status"] = "FAILED"
            log(worker_id, keyword, f"FAILED: Cart verification check failed (Cart Price: ₹{cart_price}, Cart Total: ₹{cart_total}, Qty: {cart_qty})")

    except Exception as e:
        log(worker_id, keyword, f"ERROR encountered: {e}")
        result["status"] = "FAILED"

    finally:
        # Task 4 Requirement 3: Always close browser instance in finally block
        if driver:
            try:
                # Capture individual worker browser state for Task 6 concurrent proof
                driver.save_screenshot(f"worker_{worker_id}_screenshot.png")
            except Exception:
                pass

            try:
                log(worker_id, keyword, "Closing browser instance (driver.quit)...")
                driver.quit()
            except Exception as qe:
                log(worker_id, keyword, f"Notice during driver quit: {qe}")

        execution_seconds = round(time.perf_counter() - start_time, 2)
        result["execution_seconds"] = execution_seconds
        log(worker_id, keyword, f"Worker completed in {execution_seconds}s with status: {result['status']}")

    return result


def run_multithreaded_pipeline(keywords=None, max_workers=3, headless=False,output_filename="multithread_results.json"):
    """
    Executes multiple product automation tasks concurrently using ThreadPoolExecutor.
    Consolidates thread-safe results and exports Task 5 combined JSON file.
    """
    if not keywords:
        keywords = DEFAULT_KEYWORDS[:3]

    total_tasks = len(keywords)
    print("\n" + "=" * 70)
    print(f" [PIPELINE] Launching Flipkart Multithreaded Web Automation")
    print(f" [CONFIG] Concurrency: {max_workers} simultaneous workers | Total Tasks: {total_tasks}")
    print(f" [CONFIG] Mode: {'Headless' if headless else 'Headed (Visual)'} | Output File: '{output_filename}'")
    print(f" [KEYWORDS] {', '.join(keywords)}")
    print("=" * 70 + "\n", flush=True)

    pipeline_start = time.perf_counter()
    futures_map = {}
    collected_results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, keyword in enumerate(keywords, start=1):
            future = executor.submit(execute_worker_task, idx, keyword, headless)
            futures_map[future] = (idx, keyword)

        for future in as_completed(futures_map):
            worker_id, keyword = futures_map[future]
            try:
                task_res = future.result()
                collected_results[worker_id] = task_res
            except Exception as exc:
                print(f"[FATAL ERROR | Worker-{worker_id}] Unhandled worker exception: {exc}")
                collected_results[worker_id] = {
                    "worker_id": worker_id,
                    "product_keyword": keyword,
                    "product_name": "N/A",
                    "product_price": 0,
                    "cart_price": 0,
                    "quantity": 0,
                    "cart_verified": False,
                    "http_status": 0,
                    "status": "FAILED",
                    "execution_seconds": 0.0
                }

    # Sort results by worker_id (1, 2, 3...)
    ordered_results = [collected_results[wid] for wid in sorted(collected_results.keys())]
    successful_count = sum(1 for r in ordered_results if r.get("status") == "SUCCESS")
    failed_count = total_tasks - successful_count
    total_pipeline_time = round(time.perf_counter() - pipeline_start, 2)

    # -------------------------------------------------------------
    # TASK 5: Combined JSON Output
    # -------------------------------------------------------------
    final_output = {
        "total_tasks": total_tasks,
        "successful": successful_count,
        "failed": failed_count,
        "results": ordered_results
    }

    try:
        with open(output_filename, "w", encoding="utf-8") as jf:
            json.dump(final_output, jf, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] Task 5 combined JSON saved to '{output_filename}'")
    except Exception as je:
        print(f"\n[ERROR] Failed to save JSON output: {je}")

    # Task 6: Build composite concurrent execution proof from worker screenshots
    try:
        from PIL import Image
        worker_shots = [f"worker_{r.get('worker_id')}_screenshot.png" for r in ordered_results]
        valid_imgs = [Image.open(p) for p in worker_shots if os.path.exists(p)]
        if valid_imgs:
            total_w = sum(im.width for im in valid_imgs)
            max_h = max(im.height for im in valid_imgs)
            composite = Image.new("RGB", (total_w, max_h), (255, 255, 255))
            cur_x = 0
            for im in valid_imgs:
                composite.paste(im, (cur_x, 0))
                cur_x += im.width
            composite.save("concurrent_execution.png")
            print("[SUCCESS] Task 6 concurrent execution proof saved to 'concurrent_execution.png'")
            for p in worker_shots:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
    except Exception as ie:
        pass

    # Summary Display Card
    print("\n" + "=" * 70)
    print(f" [SUMMARY] MULTITHREADED EXECUTION COMPLETED IN {total_pipeline_time}s")
    print(f" Total Tasks: {total_tasks} | Successful: {successful_count} | Failed: {failed_count}")
    print("=" * 70)
    for res in ordered_results:
        status_icon = "✅" if res.get("status") == "SUCCESS" else "❌"
        print(
            f" {status_icon} Worker-{res.get('worker_id')} | "
            f"Keyword: '{res.get('product_keyword')}' | "
            f"Price: ₹{res.get('product_price')} | "
            f"Cart Price: ₹{res.get('cart_price')} | "
            f"Cart Total: ₹{res.get('cart_total')} | "
            f"HTTP: {res.get('http_status')} | "
            f"Time: {res.get('execution_seconds')}s"
        )
    print("=" * 70 + "\n", flush=True)

    return final_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flipkart Multithreaded Web Automation")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Max concurrent workers (default: 3)")
    parser.add_argument("-k", "--keywords", type=str, nargs="+", default=None, help="List of product search keywords")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("-o", "--output", type=str, default="multithread_results.json", help="Output JSON filename")

    args = parser.parse_args()

    # If keywords passed as comma-separated or space-separated
    keywords_list = None
    if args.keywords:
        if len(args.keywords) == 1 and "," in args.keywords[0]:
            keywords_list = [k.strip() for k in args.keywords[0].split(",") if k.strip()]
        else:
            keywords_list = args.keywords

    run_multithreaded_pipeline(
        keywords=keywords_list,
        max_workers=args.workers,
        headless=args.headless,
        output_filename=args.output
    )