from playwright.sync_api import sync_playwright
import re
import os
import time

def debug_url(url):
    download_url = None
    
    with sync_playwright() as p:
        # Use headed mode (actually see the browser)
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        
        # Remove webdriver flag
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        page = context.new_page()
        
        # Log POST requests with full details
        def log_request(request):
            if request.method == "POST":
                print(f"  POST: {request.url}")
                print(f"  Headers: {dict(request.headers)}")
                if request.post_data:
                    print(f"  Body: {request.post_data[:200]}")
        
        def log_response(response):
            if response.request.method == "POST":
                print(f"  POST RESPONSE: {response.status}")
                print(f"  Response headers: {dict(response.headers)}")
                try:
                    print(f"  Response body: {response.text()[:500]}")
                except:
                    pass
        
        page.on("request", log_request)
        page.on("response", log_response)
        
        # Intercept download
        def handle_route(route):
            nonlocal download_url
            if 'dl.fuckingfast.co' in route.request.url:
                download_url = route.request.url
                print(f"\n  *** CAPTURED: {download_url}")
                route.abort()
            else:
                route.continue_()
        
        page.route("**/*", handle_route)
        
        clean_url = url.split('#')[0]
        print(f"\n[*] Loading: {clean_url}")
        page.goto(clean_url, wait_until="networkidle", timeout=60000)
        
        # Wait for Turnstile to solve
        print("[*] Waiting for Turnstile challenge...")
        time.sleep(5)
        
        # Check for turnstile token
        turnstile = page.evaluate("""() => {
            const input = document.querySelector('[name="cf-turnstile-response"]') 
                        || document.querySelector('input[value*="cf-"]');
            return input ? input.value : 'NOT FOUND';
        }""")
        print(f"[*] Turnstile token: {turnstile[:50]}..." if turnstile != 'NOT FOUND' else "[*] Turnstile token: NOT FOUND")
        
        # Check cookies
        cookies = context.cookies()
        print(f"[*] Cookies ({len(cookies)}):")
        for c in cookies:
            print(f"    {c['name']}: {c['value'][:30]}...")
        
        input("\n[*] Browser is open. Press ENTER for FIRST CLICK...")
        
        print("\n[*] FIRST CLICK...")
        page.click("a.gay-button")
        time.sleep(2)
        
        print(f"[*] Pages open: {len(context.pages)}")
        for i, pg in enumerate(context.pages):
            print(f"    Page {i}: {pg.url}")
        
        # Close popups
        for popup in context.pages[1:]:
            print(f"[*] Closing: {popup.url[:60]}")
            popup.close()
        
        input("\n[*] Press ENTER for SECOND CLICK...")
        
        print("\n[*] SECOND CLICK...")
        page.click("a.gay-button")
        time.sleep(3)
        
        print(f"\n[*] Pages open: {len(context.pages)}")
        for i, pg in enumerate(context.pages):
            print(f"    Page {i}: {pg.url}")
        
        print(f"\n[*] Download URL: {download_url}")
        
        input("\n[*] Press ENTER to close...")
        browser.close()
    
    return download_url

url = input("Paste URL: ").strip()
debug_url(url)