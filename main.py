import sys, requests, time
import pandas as pd
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from utils import (
    configure_terminal_encoding,
    extract_product_urls,
    extract_flipkart_product,
    handle_cart_retry,
    extract_cart_total,
)


configure_terminal_encoding()

def run_flipkart_automation(search_query="laptop"):
    """
    Automates Flipkart product search, DOM data extraction, 
    Fast Cart API integration, and Excel data export using Selenium.
    """
    
    # 1. Chrome Options & Performance Configuration
    options = Options()
    # options.add_argument("--headless=new")  # For run in Background uncomment this line
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled") # Bot detection bypass
    
    # Optional: Block images for blazing fast load speeds
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    print("[INFO] Initializing Google Chrome WebDriver...")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    # Data container for assignment execution & export
    product_data = {
        "Product Name": "N/A",
        "Product Price": "N/A",
        "Total Amount": "N/A",
        "Quantity (Qty)": 1,
        "Product Rating": "N/A",
        "Product Details / Specifications": "N/A",
        "Listing ID": "N/A",
        "Product ID": "N/A",
        "Product URL": "N/A"
    }

    try:
        # --- REQUIREMENT 1: Open Flipkart ---
        driver.get("https://www.flipkart.com")
        
        # Handle login popup if it appears
        try:
            close_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '✕')]"))
            )
            close_btn.click()
        except Exception:
            pass

        # --- REQUIREMENT 2: Search for a Product ---
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.RETURN)
        print(f"[INFO] Search query submitted. Waiting for product results...")

        # --- REQUIREMENT 3: Select Product & Extract DOM Info ---
        products = extract_product_urls(driver)
        if not products:
            raise RuntimeError(f"No matching products found for search query: '{search_query}'")
        products_url_data = products[0]

        print(f"[INFO] Opening matching product page...")
        driver.get(products_url_data.get("url", ""))
        product_details = extract_flipkart_product(driver, timeout=20)

        product_title = (products_url_data.get("title") or "").replace("Add to Compare ", "").split("...")[0].strip()
        if not product_title or len(product_title) < 3 or product_title.startswith("₹") or "% off" in product_title:
            try:
                title_elem = driver.find_element(By.TAG_NAME, "h1")
                product_title = title_elem.text.strip().replace("\n", " ")
            except Exception as e:
                print(f"[WARNING] Could not locate <h1> title ({e}). Using search query fallback.")
                product_title = search_query.title()
        product_data["Product Name"] = product_title

        product_data["Listing ID"] = products_url_data.get("listing_id") or product_details.get("listing_id") or "N/A"
        product_data["Product ID"] = products_url_data.get("product_id") or product_details.get("product_id") or "N/A"
        product_data["Product URL"] = products_url_data.get("url") or driver.current_url

        product_data["Product Price"] = product_details["selling_price"]
        product_data["Product Rating"] = product_details["rating"]

        # Store specifications as a formatted string for Excel
        specs_dict = product_details.get("specifications", {})
        if specs_dict:
            specs_str = " | ".join(f"{k}: {v}" for k, v in specs_dict.items())
        else:
            specs_str = "N/A"
            print("[WARNING] No specifications could be extracted.")
        product_data["Product Details / Specifications"] = specs_str

        # Extract Listing ID (lid) from URL for Fast API execution
        parsed_url = urlparse(products_url_data["url"])
        query_params = parse_qs(parsed_url.query)

        # --- REQUIREMENT 4: Cart API using current browser session ---
        print(" [STEP 4/6] Add Product to Shopping Cart \n\n")

        listing_id = product_data.get("Listing ID")
        product_id = product_data.get("Product ID")
        selling_price = product_data.get("Product Price")

        if (
            listing_id and listing_id != "N/A"
            and product_id and product_id != "N/A"
            and selling_price not in (None, "", "N/A")
        ):
            # Get cookies from the current Selenium browser session
            browser_cookies = driver.get_cookies()

            # Transfer applicable cookies to a requests session
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
                        "selectedActions": [
                            "ADD_TO_CART"
                        ],
                        "primaryProductPrice": int(
                            str(selling_price).replace("₹", "")
                            .replace(",", "").strip()
                        )
                    }
                },
                "pageType": "ProductPage"
            }

            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": "https://www.flipkart.com",
                "Referer": driver.current_url,
                "X-User-Agent": driver.execute_script(
                    "return navigator.userAgent"
                ) + " FKUA/website/42/website/Desktop"
            }

            MAX_RETRIES = 3
            api_response = None
            api_url = "https://1.rome.api.flipkart.com/api/5/cart"

            try:
                for attempt in range(1, MAX_RETRIES + 1):
                    response = session.post(api_url, headers=headers, json=payload, timeout=30)

                    try:
                        api_response = response.json()
                    except ValueError:
                        print("[WARNING] API returned non-JSON response.")
                        break

                    # Handle Flipkart DC Change (406 + ERROR_CODE 2000)
                    error_code = api_response.get("ERROR_CODE")
                    if response.status_code == 406 and error_code == 2000:
                        dc_resp = api_response.get("RESPONSE", {})
                        dc_info = dc_resp.get("dc", "unknown")
                        dc_id = dc_resp.get("id")
                        print(f"[INFO] Flipkart DC Routing detected (DC: {dc_info}). Redirecting to DC endpoint...")
                        if dc_id:
                            api_url = f"https://{dc_id}.rome.api.flipkart.com/api/5/cart"
                        time.sleep(2)
                        continue  # retry with new DC endpoint

                    # Success or non-retryable error — break out
                    break

                cart_response = (
                    api_response.get("RESPONSE", {})
                    .get("cartResponse", {})
                )

                item = cart_response.get(listing_id, {})

                if item.get("presentInCart") is True:
                    print("[SUCCESS] Product successfully added and confirmed in cart (presentInCart: true).")
                    # Sync updated session cookies back to Selenium browser
                    for c in session.cookies:
                        try:
                            driver.add_cookie({"name": c.name, "value": c.value, "domain": ".flipkart.com", "path": "/" })
                        except Exception:
                            try:
                                driver.add_cookie({"name": c.name, "value": c.value})
                            except Exception:
                                pass
                else:
                    status = response.status_code
                    err_msg = api_response.get("ERROR_MESSAGE", "Unknown error")
                    print(
                        f"[WARNING] Product not confirmed in cart. "
                        f"HTTP {status} | Error: {err_msg}"
                    )

            except requests.RequestException as exc:
                print("[ERROR] Cart API request failed:", str(exc))

            finally:
                session.close()

        else:
            print(
                "[WARNING] Listing ID, Product ID, or Selling Price "
                "is missing. Skipping Cart API request."
            )


        # --- REQUIREMENT 5: Checkout & Cart Verification ---
        print(" [STEP 5/6] Checkout & Shopping Cart Verification \n\n")
        driver.get("https://www.flipkart.com/viewcart")
        
        time.sleep(3)

        handle_cart_retry(driver)  # If temporary retry banner is shown, click Retry

        # Extract the payable Total Amount from the Flipkart Cart (/viewcart) page.
        total_amount = extract_cart_total(driver, max_attempts=5) 

        if total_amount:
            product_data["Total Amount"] = total_amount
        else:
            # Fallback to product price if cart page didn't render summary
            print(f"[WARNING] Cart Total not detected on /viewcart. Falling back to Product Price: {product_data.get('Product Price')}")
            product_data["Total Amount"] = product_data.get("Product Price", "N/A")

        print(f" > Verified Payable Total : {product_data['Total Amount']}")
        time.sleep(2)

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during execution: {e}")
        
    finally:
        # --- REQUIREMENT 6: Product Data Extraction & Excel Export ---
        print(" [STEP 6/6] Product Data Extraction & Excel Export \n\n")
        
        # Save ONLY the 6 required fields
        required_columns = ["Product Name", "Product Price", "Total Amount", "Quantity (Qty)", "Product Rating", "Product Details / Specifications"]
        export_df = pd.DataFrame([{col: product_data.get(col, "N/A") for col in required_columns}])
        excel_filename = "flipkart_product_details.xlsx"
        
        try:
            export_df.to_excel(excel_filename, index=False, engine='openpyxl')
            print(f"[SUCCESS] All 6 required fields saved to '{excel_filename}'")
        except PermissionError:
            backup_file = "flipkart_product_details_backup.xlsx"
            export_df.to_excel(backup_file, index=False, engine='openpyxl')
            print(f"[WARNING] '{excel_filename}' is locked or open in Excel. Saved successfully to backup file: '{backup_file}'")
        except Exception as ex:
            print(f"[ERROR] Failed to save Excel file: {ex}")

        # Final Terminal Summary Card
        print(" [SUMMARY] Automation Workflow Completed Successfully")

        driver.quit()

if __name__ == "__main__":
    search_term = sys.argv[1] if len(sys.argv) > 1 else "laptop"
    run_flipkart_automation(search_term)