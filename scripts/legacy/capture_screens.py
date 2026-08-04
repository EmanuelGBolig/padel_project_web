import asyncio
from playwright.async_api import async_playwright
import os

ARTIFACTS_DIR = r"C:\Users\egome\.gemini\antigravity\brain\89629173-688d-43b9-afa7-f3087e757976"

async def capture_screens():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # Mobile Viewport (iPhone 13 Pro)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            is_mobile=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
        )
        
        page = await context.new_page()
        
        try:
            print("Logging in...")
            await page.goto("http://127.0.0.1:8000/accounts/login/")
            await page.wait_for_timeout(1000)
            await page.fill('input[type="email"], input[name="username"]', 'test@example.com')
            await page.fill('input[type="password"]', 'password123')
            await page.click('button:has-text("Ingresar")')
            await page.wait_for_timeout(2000)
            
            print("Capturing Hamburger Menu...")
            # Go to home and open menu
            await page.goto("http://127.0.0.1:8000/")
            await page.wait_for_timeout(1000)
            
            # Find the hamburger menu - DaisyUI/Tailwind mobile menus usually have a specific button
            # We'll try to find a button with an SVG inside it that triggers the drawer/dropdown
            menu_btn = page.locator("label.drawer-button, button.btn.btn-square.btn-ghost").first
            if await menu_btn.count() > 0:
                await menu_btn.click()
                await page.wait_for_timeout(1000)
                await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "real_mobile_menu_open.png"))
            else:
                 # Fallback, just take a screenshot anyway
                 await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "real_mobile_menu_open_fallback.png"))

            print("Capturing Crear Equipo with Data...")
            await page.goto("http://127.0.0.1:8000/equipos/crear/")
            await page.wait_for_timeout(2000)
            # Try to interact with the form slightly to make it look active
            await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "real_mobile_crear_equipo_active.png"))
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_screens())
