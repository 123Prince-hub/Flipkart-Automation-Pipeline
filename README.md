# Flipkart E-Commerce Automation Pipeline

A  Python automation framework built with **Selenium WebDriver**, **Requests**, and **Pandas**. It automates searching products on Flipkart, parses deep technical specifications from modern dynamic DOM grids, adds products to the shopping cart via high-speed internal APIs, verifies final checkout pricing on the cart page, and exports structured records into an Excel spreadsheet.

---

## 📌 System Requirements (What is Needed?)

Before running this project, ensure you have:
1. **Operating System:** Windows 10/11, macOS, or Linux.
2. **Python:** Python 3.12 or higher installed ([Download Python](https://www.python.org/downloads/)).
3. **Google Chrome Browser:** Any modern version of Chrome installed (WebDriver is auto-managed).
4. **Active Internet Connection:** Required to interact with Flipkart in real-time.

---

## 🚀 Quick Start (1-Click Run)

You do **NOT** need to manually create virtual environments or install pip packages. The included `run.py` utility manages everything automatically via `subprocess`:

```bash
# 1. Clone or open the project folder
cd Flipkart_Automation

# 2. Run with default product ('laptop')
python run.py

# 3. Or pass any search keyword directly from the terminal:
python run.py mobile
python run.py "smart watch"
python run.py jeans
python run.py headphones
```

> **Note:** If `venv` already exists and dependencies are installed, `run.py` detects this instantly and skips re-installation, launching the automation in under 0.1 seconds.

---

## 📋 Assignment Requirements Compliance (`rules.md`)

| Step | Requirement | Status | Engineering Implementation Details |
| :---: | :--- | :---: | :--- |
| **1** | **Open Flipkart** | ✅ | Automated via `ChromeDriverManager`. Bypasses bot detection flags and auto-closes login modals. |
| **2** | **Search for Product** | ✅ | Accepts dynamic query (`laptop`, `mobile`, `jeans`, etc.) with explicit `WebDriverWait` for elements. |
| **3** | **Select Product** | ✅ | Opens in-stock product, extracts verified Title, Price, Rating, and 20–80+ specifications. |
| **4** | **Add to Cart** | ✅ | High-speed internal Rome Cart API execution with automatic Datacenter (DC) failover (`HTTP 406`). |
| **5** | **Checkout Verification** | ✅ | Navigates to `/viewcart` and verifies net payable **Total Amount** (including platform fees and discounts). |
| **6** | **Excel Export** | ✅ | Saves strictly the required 6 columns to `flipkart_product_details.xlsx` with openpyxl. |

---

## ⚙️ How the Entire Pipeline Works (Step-by-Step)

```text
[Terminal / CLI]
       │
       ▼
 [run.py Runner] ────► Checks if 'venv' exists & dependencies installed
       │               (Auto-creates venv & runs pip install ONLY if missing)
       ▼
 [main.py Pipeline]
       │
       ├─► STEP 1: Launch Chrome WebDriver with anti-detection options & navigate to Flipkart
       │
       ├─► STEP 2: Enter search query ('laptop', 'mobile', etc.) & wait for result cards
       │
       ├─► STEP 3: Prioritize in-stock item, navigate to product page & parse dynamic specifications
       │
       ├─► STEP 4: Transfer browser session cookies to Rome Cart API -> Auto-route DC -> Verify cart presence
       │
       ├─► STEP 5: Navigate to '/viewcart' & verify final net payable Total Amount (including fees)
       │
       └─► STEP 6: Export strictly the 6 required columns to 'flipkart_product_details.xlsx'
```

### Detailed Breakdown:

1. **Step 1: Open Flipkart & Bot Bypass**
   - Detects and closes login popups automatically.

2. **Step 2: Dynamic Search Execution**
   - Locates search bar using explicit waits.
   - Submits query and monitors search card availability.

3. **Step 3: Deep Data & Specification Extraction (`utils.py`)**
   - **Smart In-Stock Prioritizer:** Skips "Out of Stock" or "Coming Soon" banners to pick an active buyable product.
   - **Robust Fallbacks:** Extracts verified ratings from JSON-LD schema or rating badges, and title from `<h1>` if card text is missing.

4. **Step 4: Fast Cart API with Self-Healing DC Routing**
   - Instead of fragile UI button clicks that break when overlays appear, the engine synchronizes Selenium's session cookies.
   - Sends payload to Flipkart Cart API.
   - If Flipkart returns `HTTP 406`, the script extracts the assigned datacenter ID and dynamically re-routes to Flipkart Cart API.

5. **Step 5: Checkout & Cart Total Verification**
   - Navigates to `https://www.flipkart.com/viewcart`.
   - Inspects the live `Price Details` container and bottom checkout bar near `Place Order`.
   - Captures the true net payable **Total Amount** 

6. **Step 6: Resilient Excel Export**
   - Exports strictly the 6 required fields without polluting internal technical IDs.
   - Handles file locks gracefully: if Microsoft Excel has `flipkart_product_details.xlsx` locked, it automatically saves to a backup file without crashing.

---

## 📊 Output Data Schema (`flipkart_product_details.xlsx`)

The generated Excel file strictly contains the exact 6 columns specified in `rules.md`:

| Column Name | Sample Value | Description |
| :--- | :--- | :--- |
| **Product Name** | `Samsung Galaxy Book4 Metal Intel Core i5 13th Gen...` | Clean product title (without noisy promo text) |
| **Product Price** | `61990` | Base selling price of the selected product |
| **Total Amount** | `₹62,296` | Final payable amount verified on the Cart page |
| **Quantity (Qty)** | `1` | Cart quantity |
| **Product Rating** | `4.4` | Star rating (from JSON-LD / rating badge) |
| **Product Details / Specifications** | `Brand: Samsung \| Processor: Core i5 \| RAM: 16 GB...` | Full pipe-delimited specifications string |

---

## 💻 Manual Execution Options

If you prefer to run using standard manual environment activation:

### 1. Manual Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (macOS / Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Directly
```bash
# Run with default 'laptop'
python main.py

# Run with any category
python main.py mobile
python main.py jeans
python main.py watch
```


---

## 📁 Repository File Structure

```text
Flipkart_Automation/
├── run.py                      # 1-Click All-in-One CLI runner (auto-venv, auto-pip & execution)
├── main.py                     # Main automation script orchestrating the full 6-step workflow
├── utils.py                    # DOM specification parser, link extractor, & UI helpers
├── requirements.txt            # Python dependencies (Selenium, Pandas, OpenPyXL, Requests, etc.)
├── README.md                   # Comprehensive project documentation
```

---