# Python Multithreaded Web Automation

**Website:** [https://www.flipkart.com](https://www.flipkart.com/)  
**Estimated Duration:** 3–4 hours  
**Objective:** Enhance your previous Flipkart automation project to execute multiple product automation tasks concurrently while maintaining independent browser sessions and accurate results.

---

## Task 1 — Multithreaded Selenium Automation

Use Python's `ThreadPoolExecutor` to execute automation tasks concurrently.

### Requirements:
1. Accept a list of 3–5 product search keywords, such as:
   * Samsung mobile
   * Wireless headphones
   * Logitech mouse
   * Bluetooth speaker
   * Laptop stand
2. Create a separate Selenium Chrome browser instance for each worker.
3. Run at least 3 workers simultaneously.
4. Each worker must independently search for its assigned product, select a result, and extract the product name, price, rating, and URL.
5. Ensure that browser sessions, cookies, and WebDriver instances are not shared between threads.
6. Use a configurable `max_workers` parameter.

---

## Task 2 — Session and HTTP Requests

For each worker:
1. Extract cookies from its Selenium browser session.
2. Create a separate `requests.Session()`.
3. Transfer the relevant cookies into that worker's requests session.
4. Make a request to a public product or page endpoint.
5. Record the HTTP status code.
6. Handle failed requests, timeouts, and unexpected responses appropriately.

> **Important:** Each worker must maintain its own isolated session. Do not bypass CAPTCHA, access restrictions, or rate limits.

---

## Task 3 — Cart Automation and Verification

For each worker:
1. Attempt to add the selected product to the cart using Selenium.
2. Navigate to the shopping cart.
3. Verify that the selected product actually appears in the cart.
4. Extract the actual quantity, item price, and cart total.
5. Compare the product page information with the cart information.
6. Report `SUCCESS` only when all required cart verifications pass.

> **Important:** If a product cannot be added to the cart, report the appropriate failure reason. Do not fabricate data or incorrectly report success.

---

## Task 4 — Thread Management and Error Handling

Implement the following:
1. Use `ThreadPoolExecutor` with a configurable worker count.
2. Ensure an exception in one worker does not crash other workers.
3. Always close browser instances using `driver.quit()` in a `finally` block.
4. Handle Selenium timeouts and missing elements.
5. Maintain independent logs identifying the worker and product.
6. Collect and consolidate results safely.
7. Record individual worker execution times.

---

## Task 5 — JSON Output

Generate a combined JSON file containing the results of all workers.

### Example Schema:
```json
{
  "total_tasks": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "worker_id": 1,
      "product_keyword": "Samsung mobile",
      "product_name": "Example Samsung Mobile",
      "product_price": 15000,
      "cart_price": 15000,
      "cart_total": 15000,
      "quantity": 1,
      "cart_verified": true,
      "http_status": 200,
      "status": "SUCCESS",
      "execution_seconds": 21.5
    }
  ]
}
```

> **Rule:** All actual product and cart values must be extracted from the website. Do not use hardcoded prices, product titles, quantities, or success statuses.

---

## Task 6 — Submission

Update your existing GitHub repository and provide:
* Complete Python source code
* `requirements.txt`
* `README.md` with execution instructions
* Sample JSON output for at least 3 product tasks
* Screenshot or short screen recording showing concurrent browser execution