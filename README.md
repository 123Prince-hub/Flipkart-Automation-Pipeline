# Flipkart Automation Pipeline

A robust Python automation framework built with **Selenium WebDriver**, **Requests**, and **Pandas**. It automates product discovery on Flipkart, parses deep technical specifications, adds products to the cart via high-speed internal APIs with smart UI fallback, verifies payable totals on the cart page, and exports structured records into Excel.

---

## 📌 System Requirements

1. **Operating System:** Windows 10/11, macOS, or Linux
2. **Python:** Python 3.10 or higher installed
3. **Google Chrome:** Any modern version (ChromeDriver is automatically managed)
4. **Internet Connection:** Active connection for live Flipkart interaction

---

## 🚀 Quick Start (1-Click Run)

No manual virtual environment setup or dependency installation is required. `run.py` handles environment creation and package installation automatically:

```bash
# 1. Open project directory
cd Flipkart_Automation

# 2. Run with default search query ('laptop')
python run.py

# 3. Or pass any search query directly:
python run.py mobile
python run.py watch
python run.py jeans
python run.py milk
python run.py sugar
```

---

## 📋 Assignment Requirements Compliance (`rules.md`)

| Step | Requirement | Implementation Details | Status |
| :---: | :--- | :--- | :---: |
| **1** | **Open Flipkart** | Launches Chrome via `webdriver-manager`, bypasses bot detection flags, and auto-dismisses login modals. | ✅ Complete |
| **2** | **Search for Product** | Searches dynamic keywords (`laptop`, `mobile`, `milk`, etc.) with explicit `WebDriverWait` and fallback locators. | ✅ Complete |
| **3** | **Select Product** | Prioritizes in-stock listings, navigates to product page, and parses title, price, ratings, and full specifications. | ✅ Complete |
| **4** | **Add to Cart** | High-speed internal Rome Cart API execution with auto DC failover (`HTTP 406`) + DOM UI button fallback for Grocery/FMCG. | ✅ Complete |
| **5** | **Checkout Verification** | Navigates to `/viewcart`, handles retry banners, auto-switches grocery tabs if needed, and verifies net payable **Total Amount**. | ✅ Complete |
| **6** | **Excel Export** | Exports strictly the 6 required fields to `flipkart_product_details.xlsx` with timestamped backup if file is open. | ✅ Complete |

---

## 🛡️ Key Robustness & Edge-Case Features

- **Multi-Category Resilient:** Fully tested across Electronics (`laptop`, `mobile`), Lifestyle/Fashion (`watch`, `jeans`), and Grocery/FMCG (`milk`, `sugar`).
- **Hybrid Add-to-Cart Engine:** Executes high-speed internal Rome API by default; seamlessly falls back to browser-level UI click (`add_to_cart_ui_fallback`) if API is restricted.
- **Dynamic DC Routing:** Automatically handles Flipkart Rome Datacenter shifts (`HTTP 406 + ERROR_CODE 2000`) and redirects requests to the assigned DC.
- **Terminal Unicode Protection:** Includes `configure_terminal_encoding()` to ensure Indian Rupee symbols (`₹`) and special characters print without `charmap` codec crashes on Windows consoles.
- **Lock-Safe Excel Export:** If `flipkart_product_details.xlsx` is currently open in Microsoft Excel, it automatically writes to a timestamped backup file to prevent `PermissionError` crashes.

---

## 📊 Output Data Schema (`flipkart_product_details.xlsx`)

The output spreadsheet strictly exports the exact 6 columns specified in `rules.md`:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| **Product Name** | Text | Clean product title |
| **Product Price** | Number | Base selling price of the product |
| **Total Amount** | Text | Verified net payable amount from Cart page (e.g. `₹70,296`) |
| **Quantity (Qty)** | Number | Verified cart quantity (`1`) |
| **Product Rating** | Number | Rating value (e.g. `4.2`) from JSON-LD / rating badge |
| **Product Details / Specifications** | Text | Pipe-delimited key-value specifications string |

---

## 💻 Manual Execution (Alternative)

If you prefer running without the 1-click runner:

```bash
# 1. Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run automation directly
python main.py "laptop"
python main.py "mobile"
```

---

## 📁 Repository Structure

```text
Flipkart_Automation/
├── run.py                          # 1-Click CLI runner (auto-venv, auto-pip, cross-platform)
├── main.py                         # Main automation workflow (Steps 1 to 6)
├── utils.py                        # Modular helper functions (specs, links, retry, cart total)
├── requirements.txt                # Project dependencies (Selenium, Pandas, OpenPyXL, Requests)
├── flipkart_product_details.xlsx   # Sample generated output Excel file
├── README.md                       # Documentation & execution guide
└── rules.md                        # Original assignment specification
```

---

## 👨‍💻 Developer & Author

**Prince Kirad**  
*Python & Web Automation Engineer*

[![Email](https://img.shields.io/badge/Email-princekirad11%40gmail.com-ea4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:princekirad11@gmail.com)

> *Crafted with clean code, robust exception handling, and real-world resilience.*